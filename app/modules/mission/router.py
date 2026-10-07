"""Module E: mission preparation (questions, witnesses, checklist, guide PDF)."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.latex import LatexError, render_pdf
from app.db import get_db
from app.modules.audit.service import log_action
from app.modules.cases.router import get_case_or_404
from app.modules.contracts.router import output_dir

router = APIRouter(prefix="/mission", tags=["E - Mission"])

QUESTIONS_TEMPLATES = {
    "fraude_bancaire": [
        "Pouvez-vous decrire les virements suspects ?",
        "Avez-vous acces aux logs bancaires ?",
        "Qui avait acces au compte ?",
        "Quelle est la periode concernee ?",
        "Des alertes ont-elles ete declenchees ?",
    ],
    "intrusion_reseau": [
        "Quand l'intrusion a-t-elle ete detectee ?",
        "Quels systemes sont compromis ?",
        "Avez-vous des logs firewall/IDS ?",
        "Des donnees ont-elles ete exfiltrees ?",
        "Y a-t-il eu une demande de rancon ?",
    ],
    "malware": [
        "Quand le comportement anormal a-t-il ete observe pour la premiere fois ?",
        "Quelle piece jointe ou lien a ete ouvert, et a quelle heure ?",
        "Quels serveurs et partages de fichiers sont touches ?",
        "Existe-t-il des sauvegardes saines et recentes ?",
        "Un message de rancon ou une extension de fichier inhabituelle est-il apparu ?",
    ],
}
GENERIC = [f"Question generique {i}" for i in range(1, 6)]
CHECKLIST = ["Identifier les sources de preuves", "Preparer le materiel forensique",
             "Hacher les preuves des la collecte (SHA-256)", "Rediger les PV"]


def generate_questions(case_type: str) -> dict:
    return {"questions": QUESTIONS_TEMPLATES.get(case_type, GENERIC),
            "suggested_witnesses": [], "checklist": CHECKLIST}


class PrepareIn(BaseModel):
    case_id: str


@router.post("/prepare")
def prepare(body: PrepareIn, db: Session = Depends(get_db)):
    case = get_case_or_404(db, body.case_id)
    if case.chosen_expert_id is None:
        raise HTTPException(409, "No expert has been selected for this case")
    result = generate_questions(case.case_type)
    try:
        pdf = render_pdf("guide.tex.j2", {"case_id": case.id, "case_type": case.case_type, **result},
                         output_dir() / "guides" / case.id, "guide")
    except LatexError as e:
        raise HTTPException(500, "Guide generation failed") from e
    log_action(db, "E", "prepare_mission", case_id=case.id, file_path=str(pdf))
    return {**result, "guide_pdf_url": f"/api/v1/mission/{case.id}/guide.pdf"}


@router.get("/{case_id}/guide.pdf")
def guide(case_id: str, db: Session = Depends(get_db)):
    get_case_or_404(db, case_id)
    pdf = Path(output_dir() / "guides" / case_id / "guide.pdf")
    if not pdf.is_file():
        raise HTTPException(404, "Guide not generated yet")
    return FileResponse(pdf, media_type="application/pdf", filename="guide.pdf")
