"""Module K: explanations of the algorithmic results, in plain French.

One endpoint answers "why?" for the three kinds of result Locard computes:
  B  an expert's matching score        (the mandataire who owns the case)
  F  a detected inconsistency          (the investigator of the case; entity_id = its position in the list, from 0)
  H  a technical report's score        (the investigator of the case; entity_id = the report id)
The numbers come from the same code that produced the result, so an explanation can never disagree with the screen.
"""
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.access import case_for
from app.modules.auth.router import current_user
from app.modules.auth.service import User
from app.modules.matching.service import W_DISPO, W_EXP, W_TEXT, Expert, match_experts
from app.modules.pv.router import _all_facts, _case_pvs
from app.modules.pv.rules import detect
from app.modules.reports.tech import analysis_for_case

router = APIRouter(prefix="/xai", tags=["K - Explainability"])

WORD = re.compile(r"[a-zà-ÿ]{4,}")


def _words(text: str) -> set[str]:
    return set(WORD.findall(text.lower().replace("_", " ")))


def _explain_expert(db: Session, user: User, case_id: str, expert_id: str) -> dict:
    if user.role != "mandataire":
        raise HTTPException(403, "Expert scores are explained to the mandataire who owns the case")
    case = case_for(db, case_id, user, "own")
    experts = list(db.scalars(select(Expert)))
    ranking = match_experts(case.description, case.case_type, experts, top_n=len(experts))
    found = next(((i, e) for i, e in enumerate(ranking, start=1) if str(e["id"]) == expert_id), None)
    if found is None:
        raise HTTPException(404, "Expert not found")
    rank, e = found
    expert = db.get(Expert, e["id"])
    shared = sorted(_words(case.description + " " + case.case_type) & _words(" ".join(expert.competences) + " " + (expert.bio or "")))
    b = e["breakdown"]
    common = f" (mots communs avec le mandat : {', '.join(shared[:8])})" if shared else " (aucun mot en commun avec le mandat)"
    return {
        "explanation": (
            f"{e['nom']} obtient {e['score']:.2f} sur 1 et se classe n° {rank} sur {len(ranking)}. "
            f"Similarité textuelle : {b['text_score']:.2f} sur {W_TEXT:.2f}{common}. "
            f"Disponibilité : {b['dispo_score']:.2f} sur {W_DISPO:.2f} ({'disponible' if e['disponibilite'] else 'indisponible'}). "
            f"Expérience : {b['exp_score']:.2f} sur {W_EXP:.2f} ({e['annees_experience']} ans, 20 ans valent le maximum)."),
        "breakdown": {"text_score": b["text_score"], "dispo_score": b["dispo_score"], "exp_score": b["exp_score"]},
        "details": {"score": e["score"], "rank": rank, "of": len(ranking), "matched_keywords": shared,
                    "weights": {"text": W_TEXT, "dispo": W_DISPO, "exp": W_EXP},
                    "formula": "0,6 × similarité TF-IDF + 0,2 × disponibilité + 0,2 × min(années / 20, 1)"},
    }


def _explain_incoherence(db: Session, user: User, case_id: str, index: str) -> dict:
    if user.role != "investigateur":
        raise HTTPException(403, "Inconsistencies are explained to the investigator of the case")
    case = case_for(db, case_id, user, "mission")
    incs = detect(_all_facts(_case_pvs(db, case.id)))
    if not index.isdigit() or int(index) >= len(incs):
        raise HTTPException(404, "Inconsistency not found")
    inc = incs[int(index)]
    return {
        "explanation": f"{inc['description']} {inc['why']}",
        "breakdown": {"type": inc["type"], "severity": inc["severity"], "pv": inc["pv_references"]},
        "details": {"rule": inc["rule"], "evidence": inc["evidence"],
                    "score_impact": "Chaque incohérence retire 0,20 au score de cohérence (minimum 0)."},
    }


def _explain_report(db: Session, user: User, case_id: str, rapport_id: str) -> dict:
    if user.role != "investigateur":
        raise HTTPException(403, "Report scores are explained to the investigator of the case")
    case = case_for(db, case_id, user, "mission")
    analysis = analysis_for_case(db, case)
    r = next((x for x in analysis["rapports"] if x["rapport_id"] == rapport_id), None)
    if r is None:
        raise HTTPException(404, "Report not found")
    d, b = r["details"], r["breakdown"]
    missing = f" (manquent : {', '.join(d['champs_manquants'])})" if d["champs_manquants"] else " (tous les champs sont remplis)"
    found = f" ({', '.join(d['concepts_trouves'])})" if d["concepts_trouves"] else " (aucun)"
    chain = "Il figure dans la chaîne optimale." if r["in_chain"] else "Il est exclu de la chaîne optimale (seuil 0,50)."
    return {
        "explanation": (
            f"Le rapport {r['rapport_id']} obtient {r['score']:.2f} sur 1 (rang {r['rank']} sur {len(analysis['rapports'])}). "
            f"Complétude : {b['completude']:.2f} sur 0,40{missing}. "
            f"Éléments techniques cités : {b['pertinence']:.2f} sur 0,30{found}. "
            f"Preuves : {b['preuves']:.2f} sur 0,30 ({d['nb_preuves']} jointe(s), 3 donnent le maximum). {chain}"),
        "breakdown": b,
        "details": {"score": r["score"], "in_chain": r["in_chain"], "weights": r["weights"], **d,
                    "formula": "0,4 × champs remplis/4 + 0,3 × concepts cités/5 + 0,3 × min(preuves/3, 1)"},
    }


EXPLAINERS = {"B": _explain_expert, "F": _explain_incoherence, "H": _explain_report}


@router.get("/explain")
def explain(module: Literal["B", "F", "H"], case_id: str, entity_id: str, user: User = Depends(current_user),
            db: Session = Depends(get_db)):
    """Explain one result of module B, F or H. `entity_id` is the expert id, the inconsistency position or the report id."""
    return {"module": module, "case_id": case_id, "entity_id": entity_id, **EXPLAINERS[module](db, user, case_id, entity_id)}
