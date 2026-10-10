"""API for the model's suggestions (module F, second detector). See semantic.py for what they are and are not.

  GET  /semantic/status                 is the feature available, and with which settings
  POST /semantic/run {case_id}          start the comparison as a background job (returns 202)
  GET  /semantic/suggestions?case_id=   the state of the last run and its suggestions

A run compares every pair of statements of the case, which can take from seconds to minutes, so it never runs
inside the request. The suggestions are stored, tied to the exact set of PVs they were computed from: if a PV is
added or replaced afterwards they are marked `stale`.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Float, Integer, String, Text, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base, SessionLocal, get_db
from app.modules.audit.service import log_action, sha256_file
from app.modules.auth.access import case_for
from app.modules.auth.router import require_role
from app.modules.auth.service import User
from app.modules.pv import semantic
from app.modules.pv.router import Pv, _all_facts, _case_pvs, _mask, _pseudonymizer
from app.modules.pv.rules import detect

router = APIRouter(prefix="/semantic", tags=["F - PV model"])

STALE_RUN = timedelta(minutes=30)  # a run "in progress" for longer died with its server process
DISCLAIMER = ("Suggestions automatiques d'un modèle de langue : incomplètes et parfois fausses. "
              "L'expert doit les vérifier. Elles ne comptent pas dans le score de cohérence.")


class SemanticRun(Base):
    __tablename__ = "semantic_runs"

    case_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(12))  # running | done | failed
    model: Mapped[str] = mapped_column(String(200))
    started_at: Mapped[str] = mapped_column(String(40))
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pv_signature: Mapped[str] = mapped_column(String(64))
    min_score: Mapped[float] = mapped_column(Float)
    cap: Mapped[int] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    stats: Mapped[str] = mapped_column(Text, default="{}")


class SemanticSuggestion(Base):
    __tablename__ = "semantic_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    pv_a: Mapped[str] = mapped_column(String(40))
    pv_b: Mapped[str] = mapped_column(String(40))
    sentence_a: Mapped[str] = mapped_column(Text)
    sentence_b: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    p_ab: Mapped[float] = mapped_column(Float)
    p_ba: Mapped[float] = mapped_column(Float)
    shared: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of the word stems the two sentences share


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _age(timestamp: str) -> timedelta:
    return datetime.now(timezone.utc) - datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _signature(pvs: list[Pv]) -> str:
    """Identifies the exact set of PVs (ids and file hashes) a run was computed from."""
    return hashlib.sha256("|".join(f"{p.pv_id}:{p.sha256}" for p in sorted(pvs, key=lambda p: p.pv_id)).encode()).hexdigest()


def _rule_pairs(pvs: list[Pv]) -> set[frozenset]:
    """Sentence pairs the rule-based detector already reports, so the model does not repeat them."""
    out = set()
    for inc in detect(_all_facts(pvs)):
        texts = [semantic.norm(e["excerpt"])[:semantic.EXCERPT] for e in inc["evidence"]]
        if len(texts) >= 2:
            out.add(frozenset(texts[:2]))
    return out


def _job(case_id: str, actor: str) -> None:
    """The background run. It owns its database session and never raises: failures are stored on the run."""
    with SessionLocal() as db:
        run = db.get(SemanticRun, case_id)
        try:
            pvs = _case_pvs(db, case_id)
            texts = {}
            for p in pvs:
                if sha256_file(p.file_path) != p.sha256:
                    raise RuntimeError(f"Integrity check failed for PV {p.pv_id}: the stored file was modified")
                texts[p.pv_id] = Path(p.file_path).read_text(encoding="utf-8")
            cfg = semantic.settings()
            found, stats = semantic.find_suggestions(
                texts, semantic.get_model(cfg["model"]), min_score=run.min_score, cap=run.cap,
                max_candidates=cfg["max_candidates"], skip=_rule_pairs(pvs))
            db.execute(delete(SemanticSuggestion).where(SemanticSuggestion.case_id == case_id))
            db.add_all(SemanticSuggestion(case_id=case_id, pv_a=s["pv_a"], pv_b=s["pv_b"], sentence_a=s["sentence_a"],
                                          sentence_b=s["sentence_b"], score=s["score"], p_ab=s["p_ab"], p_ba=s["p_ba"],
                                          shared=json.dumps(s["shared"])) for s in found)
            run.status, run.finished_at, run.stats = "done", _now(), json.dumps({**stats, "suggestions": len(found)})
            db.commit()
            log_action(db, "F", "semantic_run", case_id=case_id, user=actor,
                       data={"model": run.model, "suggestions": len(found), **stats})
        except Exception as e:  # noqa: BLE001 - a background job has nobody to raise to
            db.rollback()
            run = db.get(SemanticRun, case_id)
            run.status, run.finished_at, run.error = "failed", _now(), f"{type(e).__name__}: {e}"[:400]
            db.commit()
            log_action(db, "F", "semantic_run_failed", case_id=case_id, user=actor, data={"error": run.error})


@router.get("/status")
def status(user: User = Depends(require_role("investigateur"))):
    available, reason = semantic.availability()
    cfg = semantic.settings()
    return {"available": available, "reason": reason, "model": cfg["model"], "min_score": cfg["min_score"], "cap": cfg["cap"]}


class RunIn(BaseModel):
    case_id: str


@router.post("/run", status_code=202)
def run_model(body: RunIn, background: BackgroundTasks, user: User = Depends(require_role("investigateur")),
              db: Session = Depends(get_db)):
    case = case_for(db, body.case_id, user, "mission")
    available, reason = semantic.availability()
    if not available:
        raise HTTPException(503, reason)
    pvs = _case_pvs(db, case.id)
    if len(pvs) < 2:
        raise HTTPException(409, "Au moins deux PV sont nécessaires pour les comparer.")
    run = db.get(SemanticRun, case.id)
    if run and run.status == "running" and _age(run.started_at) < STALE_RUN:
        raise HTTPException(409, "Une analyse du modèle est déjà en cours pour ce dossier.")
    cfg = semantic.settings()
    if run is None:
        run = SemanticRun(case_id=case.id)
        db.add(run)
    run.status, run.model, run.started_at, run.finished_at = "running", cfg["model"], _now(), None
    run.pv_signature, run.min_score, run.cap, run.error, run.stats = _signature(pvs), cfg["min_score"], cfg["cap"], None, "{}"
    db.execute(delete(SemanticSuggestion).where(SemanticSuggestion.case_id == case.id))
    db.commit()
    background.add_task(_job, case.id, user.email)
    return {"status": "running"}


@router.get("/suggestions")
def suggestions(case_id: str, pseudonymize: bool = False, user: User = Depends(require_role("investigateur")),
                db: Session = Depends(get_db)):
    case = case_for(db, case_id, user, "mission")
    available, reason = semantic.availability()
    out = {"case_id": case.id, "available": available, "reason": reason, "disclaimer": DISCLAIMER,
           "status": "none", "stale": False, "model": None, "started_at": None, "finished_at": None, "error": None,
           "min_score": None, "cap": None, "stats": {}, "suggestions": []}
    run = db.get(SemanticRun, case.id)
    if run is None:
        return out
    pvs = _case_pvs(db, case.id)
    state, error = run.status, run.error
    if state == "running" and _age(run.started_at) >= STALE_RUN:
        state, error = "failed", "L'analyse a été interrompue (redémarrage du serveur ?). Relancez-la."
    rows = db.scalars(select(SemanticSuggestion).where(SemanticSuggestion.case_id == case.id)
                      .order_by(SemanticSuggestion.score.desc(), SemanticSuggestion.id)).all()
    out.update({
        "status": state, "stale": run.pv_signature != _signature(pvs), "model": run.model, "started_at": run.started_at,
        "finished_at": run.finished_at, "error": error, "min_score": run.min_score, "cap": run.cap,
        "stats": json.loads(run.stats or "{}"),
        "suggestions": [{"pv_a": r.pv_a, "pv_b": r.pv_b, "sentence_a": r.sentence_a, "sentence_b": r.sentence_b,
                         "score": r.score, "p_ab": r.p_ab, "p_ba": r.p_ba, "shared": json.loads(r.shared)} for r in rows],
    })
    return _mask(out, _pseudonymizer(pvs)) if pseudonymize else out
