"""Module H: technical reports from forensic actions, scored and chained.

Score (0 to 1) = completeness 0.4 + relevance 0.3 + evidence 0.3.
  completeness: share of the 4 required fields that are filled in (action, outils, resultats, preuves)
  relevance:    share of 5 forensic concepts mentioned in the results (hash, timestamp, log, artefact, signature)
  evidence:     number of attached evidence items, full marks from 3
The optimal chain keeps the reports scoring 0.5 or more, best first.
Unlike the sample code of the specification, an empty field does not count as present.
"""
import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base, get_db
from app.modules.audit.service import log_action
from app.modules.auth.access import case_for
from app.modules.auth.router import require_role
from app.modules.auth.service import User
from app.modules.methodology.router import FORENSIC_TOOLS, build_methodology
from app.modules.pv.router import _all_facts, _case_pvs
from app.modules.pv.rules import detect

router = APIRouter(prefix="/reports", tags=["H - Technical reports"])

REQUIRED = ("action", "outils", "resultats", "preuves")
CONCEPTS = {  # concept -> words that show it is covered
    "empreinte (hash)": ("hash", "empreinte", "sha256", "sha-256"),
    "horodatage": ("timestamp", "horodat"),
    "journaux (logs)": ("log", "journal", "journaux"),
    "artefact": ("artefact", "artifact"),
    "signature": ("signature",),
}
W_COMPLETE, W_RELEVANCE, W_EVIDENCE = 0.4, 0.3, 0.3
CHAIN_THRESHOLD = 0.5


class TechReport(Base):
    __tablename__ = "tech_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    rapport_id: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(80))
    outils: Mapped[str] = mapped_column(Text)  # JSON list
    resultats: Mapped[str] = mapped_column(Text)
    preuves: Mapped[str] = mapped_column(Text)  # JSON list
    created_at: Mapped[str] = mapped_column(String(40))


class ReportIn(BaseModel):
    rapport_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    action: str = Field(min_length=1, max_length=80)
    outils: list[str] = Field(default_factory=list, max_length=10)
    resultats: str = Field(default="", max_length=5000)
    preuves: list[str] = Field(default_factory=list, max_length=20)


class AnalyzeIn(BaseModel):
    case_id: str
    rapports: list[ReportIn] = Field(min_length=1, max_length=50)


def score_report(r: dict) -> dict:
    """Score one report and say exactly where the points came from."""
    filled = {f: bool(r.get(f) and (r[f].strip() if isinstance(r[f], str) else r[f])) for f in REQUIRED}
    missing = [f for f, ok in filled.items() if not ok]
    text = (r.get("resultats") or "").lower()
    found = [name for name, words in CONCEPTS.items() if any(w in text for w in words)]
    n_proofs = len(r.get("preuves") or [])
    completeness = sum(filled.values()) / len(REQUIRED) * W_COMPLETE
    relevance = len(found) / len(CONCEPTS) * W_RELEVANCE
    evidence = min(n_proofs / 3, 1) * W_EVIDENCE
    return {
        "score": round(completeness + relevance + evidence, 2),
        "breakdown": {"completude": round(completeness, 2), "pertinence": round(relevance, 2),
                      "preuves": round(evidence, 2)},
        "weights": {"completude": W_COMPLETE, "pertinence": W_RELEVANCE, "preuves": W_EVIDENCE},
        "details": {"champs_manquants": missing, "concepts_trouves": found,
                    "concepts_absents": [c for c in CONCEPTS if c not in found], "nb_preuves": n_proofs},
    }


def optimize_chain(scored: list[dict]) -> list[dict]:
    ranked = sorted(scored, key=lambda s: (-s["score"], s["rapport_id"]))
    return [{"rapport_id": s["rapport_id"], "action": s["action"], "score": s["score"],
             "preuves_cles": s["preuves"][:2]} for s in ranked if s["score"] >= CHAIN_THRESHOLD]


def _recommendations(scored: list[dict], planned: list[dict]) -> list[str]:
    out = []
    for s in sorted(scored, key=lambda x: x["rapport_id"]):
        if s["details"]["champs_manquants"]:
            out.append(f"Rapport {s['rapport_id']} : compléter {', '.join(s['details']['champs_manquants'])}.")
        elif s["details"]["nb_preuves"] < 3:
            out.append(f"Rapport {s['rapport_id']} : joindre au moins 3 preuves (actuellement {s['details']['nb_preuves']}).")
        if s["score"] < CHAIN_THRESHOLD:
            out.append(f"Rapport {s['rapport_id']} exclu de la chaîne optimale (score {s['score']:.2f}, seuil {CHAIN_THRESHOLD}).")
    done = {s["action"] for s in scored}
    for step in planned:
        if step["action"] not in done:
            out.append(f"Action prévue par la méthodologie et non réalisée : {step['label']} (priorité {step['priority']}).")
    return out


def analysis_for_case(db: Session, case) -> dict:
    rows = db.scalars(select(TechReport).where(TechReport.case_id == case.id).order_by(TechReport.id)).all()
    scored = []
    for row in rows:
        data = {"rapport_id": row.rapport_id, "action": row.action, "outils": json.loads(row.outils),
                "resultats": row.resultats, "preuves": json.loads(row.preuves)}
        scored.append({**data, **score_report(data)})
    ranked = sorted(scored, key=lambda s: (-s["score"], s["rapport_id"]))
    for rank, s in enumerate(ranked, start=1):
        s["rank"], s["in_chain"] = rank, s["score"] >= CHAIN_THRESHOLD
    plan = build_methodology(case.case_type, detect(_all_facts(_case_pvs(db, case.id))))["plan"]
    return {
        "case_id": case.id,
        "rapports": ranked,
        "chaine_optimale": optimize_chain(scored),
        "score_global": round(sum(s["score"] for s in scored) / len(scored), 2) if scored else None,
        "recommandations": _recommendations(scored, plan),
        "actions_connues": {k: v["label"] for k, v in FORENSIC_TOOLS.items()},
    }


@router.post("/analyze")
def analyze(body: AnalyzeIn, user: User = Depends(require_role("investigateur")), db: Session = Depends(get_db)):
    """Store (or update, by rapport_id) the technical reports, then return the ranking and the chain."""
    case = case_for(db, body.case_id, user, "mission")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    for r in body.rapports:
        row = db.scalars(select(TechReport).where(TechReport.case_id == case.id,
                                                  TechReport.rapport_id == r.rapport_id)).first()
        if row is None:
            row = TechReport(case_id=case.id, rapport_id=r.rapport_id)
            db.add(row)
        row.action, row.resultats, row.created_at = r.action.strip(), r.resultats.strip(), now
        row.outils = json.dumps([re.sub(r"\s+", " ", o).strip()[:60] for o in r.outils if o.strip()])
        row.preuves = json.dumps([re.sub(r"\s+", " ", p).strip()[:120] for p in r.preuves if p.strip()])
    db.commit()
    log_action(db, "H", "analyze_reports", case_id=case.id, user=user.email,
               data={"rapports": [r.rapport_id for r in body.rapports]})
    return analysis_for_case(db, case)


@router.get("/analysis")
def analysis(case_id: str, user: User = Depends(require_role("investigateur")), db: Session = Depends(get_db)):
    return analysis_for_case(db, case_for(db, case_id, user, "mission"))


@router.delete("/{rapport_id}", status_code=204)
def delete_report(rapport_id: str, case_id: str, user: User = Depends(require_role("investigateur")),
                  db: Session = Depends(get_db)):
    case = case_for(db, case_id, user, "mission")
    row = db.scalars(select(TechReport).where(TechReport.case_id == case.id,
                                              TechReport.rapport_id == rapport_id)).first()
    if row is None:
        raise HTTPException(404, "Report not found")
    db.delete(row)
    db.commit()
    log_action(db, "H", "delete_report", case_id=case.id, user=user.email, data={"rapport_id": rapport_id})
