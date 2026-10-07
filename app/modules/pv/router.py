"""Module F: PV (interview report) ingestion and inconsistency detection."""
import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base, get_db
from app.modules.audit.service import log_action, sha256_file
from app.modules.cases.router import get_case_or_404
from app.modules.contracts.router import output_dir
from app.modules.pv.nlp import analyze_text, fold, person_key
from app.modules.pv.rules import detect

router = APIRouter(prefix="/pv", tags=["F - PV"])


class Pv(Base):
    __tablename__ = "pvs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    pv_id: Mapped[str] = mapped_column(String(40))
    witness_name: Mapped[str] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    analysis: Mapped[str] = mapped_column(Text)  # JSON: entities + facts
    analyzed_at: Mapped[str] = mapped_column(String(40))


class PvIn(BaseModel):
    case_id: str
    pv_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    pv_text: str = Field(min_length=20, max_length=200_000)
    witness_name: str = Field(min_length=2, max_length=100)
    pseudonymize: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _case_pvs(db: Session, case_id: str) -> list[Pv]:
    return list(db.scalars(select(Pv).where(Pv.case_id == case_id).order_by(Pv.id)))


def _pseudonymizer(pvs: list[Pv]):
    """RGPD: replace every person name (full name and surname) by 'Personne A', 'Personne B'..."""
    labels: dict[str, str] = {}
    variants: dict[str, str] = {}
    for pv in pvs:
        names = json.loads(pv.analysis)["entities"]["personnes"] + [pv.witness_name]
        for name in names:
            key = person_key(name)
            if key and key not in labels:
                labels[key] = f"Personne {chr(65 + len(labels) % 26)}{len(labels) // 26 or ''}"
            if key:
                for variant in {name.strip(), key, *name.split()}:
                    if len(variant) >= 3:
                        variants[fold(variant)] = labels[key]
    if not variants:
        return lambda s: s
    rx = re.compile("|".join(re.escape(v) for v in sorted(variants, key=len, reverse=True)), re.I)

    def apply(text: str) -> str:
        folded = fold(text)
        out, last = [], 0
        for m in rx.finditer(folded):
            out.append(text[last:m.start()] + variants[m.group().lower()])
            last = m.end()
        return "".join(out) + text[last:]
    return apply


def _all_facts(pvs: list[Pv]) -> list[dict]:
    return [f for pv in pvs for f in json.loads(pv.analysis)["facts"]]


def _score(n: int) -> float:
    return round(max(0.0, 1 - 0.2 * n), 2)


def _mask(obj, fn):
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [_mask(x, fn) for x in obj]
    if isinstance(obj, dict):
        return {k: _mask(v, fn) for k, v in obj.items()}
    return obj


@router.post("/analyze")
def analyze(body: PvIn, db: Session = Depends(get_db)):
    case = get_case_or_404(db, body.case_id)
    started = datetime.now(timezone.utc)
    result = analyze_text(body.pv_text, body.pv_id, body.witness_name, int(case.created_at[:4]))

    # The raw PV is stored and hashed on receipt (ISO/IEC 27037: collect, then hash immediately).
    folder = output_dir() / "pv" / case.id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{body.pv_id}.txt"
    path.write_text(body.pv_text, encoding="utf-8")
    digest = sha256_file(str(path))

    row = db.scalars(select(Pv).where(Pv.case_id == case.id, Pv.pv_id == body.pv_id)).first()
    if row is None:
        row = Pv(case_id=case.id, pv_id=body.pv_id)
        db.add(row)
    row.witness_name, row.file_path, row.sha256 = body.witness_name, str(path), digest
    row.analysis, row.analyzed_at = json.dumps(result), _now()
    db.flush()

    pvs = _case_pvs(db, case.id)
    mine = [i for i in detect(_all_facts(pvs)) if body.pv_id in i["pv_references"]]
    log_action(db, "F", "analyze_pv", case_id=case.id, file_path=str(path),
               data={"pv_id": body.pv_id, "incoherences": len(mine), "pseudonymized": body.pseudonymize})
    db.commit()

    response = {"pv_id": body.pv_id, "entities": result["entities"], "incoherences": mine,
                "score_coherence": _score(len(mine)), "sha256": digest, "analyzed_at": row.analyzed_at,
                "duration_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000)}
    return _mask(response, _pseudonymizer(pvs)) if body.pseudonymize else response


@router.get("")
def list_pvs(case_id: str, db: Session = Depends(get_db)):
    get_case_or_404(db, case_id)
    return {"case_id": case_id, "pvs": [
        {"pv_id": p.pv_id, "witness_name": p.witness_name, "sha256": p.sha256, "analyzed_at": p.analyzed_at}
        for p in _case_pvs(db, case_id)]}


@router.get("/report")
def report(case_id: str, pseudonymize: bool = False, db: Session = Depends(get_db)):
    """Consolidated view: entities per PV and every inconsistency found across the case."""
    get_case_or_404(db, case_id)
    pvs = _case_pvs(db, case_id)
    incs = detect(_all_facts(pvs))
    out = {"case_id": case_id,
           "pvs": [{"pv_id": p.pv_id, "witness_name": p.witness_name, "sha256": p.sha256,
                    "entities": json.loads(p.analysis)["entities"]} for p in pvs],
           "incoherences": incs, "score_coherence": _score(len(incs))}
    return _mask(out, _pseudonymizer(pvs)) if pseudonymize else out
