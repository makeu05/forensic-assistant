"""Module C: mandate/contract PDF generation (LaTeX) with SHA-256 integrity hash."""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.files import Encoding, file_answer
from app.core.latex import LatexError, render_pdf
from app.db import Base, get_db
from app.modules.audit.service import log_action, sha256_file
from app.modules.auth.access import case_for
from app.modules.auth.router import current_user, require_role
from app.modules.auth.service import User
from app.modules.cases.router import is_signed
from app.modules.matching.service import Expert

router = APIRouter(prefix="/contracts", tags=["C - Contracts"])


def output_dir() -> Path:
    return Path(os.getenv("OUTPUT_DIR", "output"))


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    pdf_path: Mapped[str] = mapped_column(String(500))
    hash_sha256: Mapped[str] = mapped_column(String(64))
    generated_at: Mapped[str] = mapped_column(String(40))


class GenerateIn(BaseModel):
    case_id: str


@router.post("/generate", status_code=201)
def generate(body: GenerateIn, user: User = Depends(require_role("mandataire")), db: Session = Depends(get_db)):
    case = case_for(db, body.case_id, user, "own")
    if case.chosen_expert_id is None:
        raise HTTPException(409, "No expert has been selected for this case")
    if not is_signed(db, case.id):
        raise HTTPException(409, "The mandate must be signed by the mandataire first")
    expert = db.get(Expert, case.chosen_expert_id)
    now = datetime.now(timezone.utc)
    cid = str(uuid.uuid4())
    try:
        pdf = render_pdf("mandat.tex.j2", {
            "case_id": case.id, "case_type": case.case_type, "priority": case.priority,
            "description": case.description, "date": now.strftime("%d/%m/%Y"),
            "mandataire": {"nom": case.mandataire_nom, "fonction": case.mandataire_fonction},
            "expert": {"nom": expert.nom, "email": expert.email, "competences": expert.competences},
        }, output_dir() / "contracts" / cid, "mandat")
    except LatexError as e:
        log_action(db, "C", "generate_contract_failed", case_id=case.id, user=user.email, data={"error": str(e)[:300]})
        raise HTTPException(500, "Contract generation failed") from e

    c = Contract(id=cid, case_id=case.id, pdf_path=str(pdf), hash_sha256=sha256_file(str(pdf)),
                 generated_at=now.isoformat(timespec="seconds").replace("+00:00", "Z"))
    db.add(c)
    db.commit()
    log_action(db, "C", "generate_contract", case_id=case.id, user=user.email, file_path=str(pdf))
    return {"contract_id": c.id, "pdf_url": f"/api/v1/contracts/{c.id}/download",
            "hash_sha256": c.hash_sha256, "generated_at": c.generated_at}


@router.get("")
def contract_for_case(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case_for(db, case_id, user, "view")
    c = db.scalars(select(Contract).where(Contract.case_id == case_id)
                   .order_by(Contract.generated_at.desc()).limit(1)).first()
    if not c:
        raise HTTPException(404, "No contract for this case")
    return {"contract_id": c.id, "pdf_url": f"/api/v1/contracts/{c.id}/download",
            "hash_sha256": c.hash_sha256, "generated_at": c.generated_at}


@router.get("/{contract_id}/download")
def download(contract_id: str, encoding: Encoding = "raw", user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Contract, contract_id)
    if not c or not Path(c.pdf_path).is_file():
        raise HTTPException(404, "Contract not found")
    case_for(db, c.case_id, user, "view")
    if sha256_file(c.pdf_path) != c.hash_sha256:
        raise HTTPException(409, "Integrity check failed: stored PDF was modified")
    return file_answer(c.pdf_path, "application/pdf", "mandat.pdf", encoding)
