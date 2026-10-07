"""Module A backend: mandate (case) creation and tracking."""
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base, get_db
from app.modules.audit.service import log_action
from app.modules.matching.router import run_matching

router = APIRouter(prefix="/cases", tags=["A - Cases"])

CaseType = Literal["fraude_bancaire", "intrusion_reseau", "malware"]
Status = Literal["en_attente", "en_cours", "termine"]


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_type: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10))
    mandataire_nom: Mapped[str] = mapped_column(String(100))
    mandataire_fonction: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="en_attente")
    chosen_expert_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))


class MandateSignature(Base):
    """Simple electronic signature of the mandate by the mandataire."""
    __tablename__ = "mandate_signatures"

    case_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    signed_by: Mapped[str] = mapped_column(String(100))
    signed_at: Mapped[str] = mapped_column(String(40))


def is_signed(db: Session, case_id: str) -> bool:
    return db.get(MandateSignature, case_id) is not None


class SignIn(BaseModel):
    signatory_name: str = Field(min_length=2, max_length=100)


class Mandataire(BaseModel):
    nom: str = Field(min_length=1, max_length=100)
    fonction: str = Field(min_length=1, max_length=100)


class CaseIn(BaseModel):
    case_type: CaseType
    description: str = Field(min_length=10)
    priority: Literal["basse", "moyenne", "haute"]
    mandataire: Mandataire


def serialize(c: Case) -> dict:
    return {
        "case_id": c.id,
        "case_type": c.case_type,
        "description": c.description,
        "priority": c.priority,
        "status": c.status,
        "created_at": c.created_at,
        "mandataire": {"nom": c.mandataire_nom, "fonction": c.mandataire_fonction},
        "chosen_expert_id": c.chosen_expert_id,
    }


def get_case_or_404(db: Session, case_id: str) -> Case:
    c = db.get(Case, case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    return c


@router.post("", status_code=201)
def create_case(body: CaseIn, db: Session = Depends(get_db)):
    c = Case(
        id=str(uuid.uuid4()),
        case_type=body.case_type,
        description=body.description,
        priority=body.priority,
        mandataire_nom=body.mandataire.nom,
        mandataire_fonction=body.mandataire.fonction,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    db.add(c)
    db.commit()
    log_action(db, "A", "create_case", case_id=c.id, user=body.mandataire.nom,
               data={"case_type": c.case_type, "priority": c.priority})
    return {"case_id": c.id}


@router.get("")
def list_cases(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 50))
    rows = db.scalars(select(Case).order_by(Case.created_at.desc()).limit(limit).offset(offset)).all()
    signed = set(db.scalars(select(MandateSignature.case_id)))
    return {
        "total": db.scalar(select(func.count()).select_from(Case)),
        "cases": [{**serialize(c), "signed": c.id in signed} for c in rows],
    }


@router.get("/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    c = get_case_or_404(db, case_id)
    return {**serialize(c), "signed": is_signed(db, c.id)}


@router.post("/{case_id}/sign")
def sign_mandate(case_id: str, body: SignIn, db: Session = Depends(get_db)):
    c = get_case_or_404(db, case_id)
    existing = db.get(MandateSignature, c.id)
    if existing:
        return {"signed": True, "signed_by": existing.signed_by, "signed_at": existing.signed_at}
    sig = MandateSignature(
        case_id=c.id, signed_by=body.signatory_name.strip(),
        signed_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    db.add(sig)
    db.commit()
    log_action(db, "A", "sign_mandate", case_id=c.id, user=sig.signed_by)
    return {"signed": True, "signed_by": sig.signed_by, "signed_at": sig.signed_at}


@router.get("/{case_id}/experts")
def case_experts(case_id: str, db: Session = Depends(get_db)):
    c = get_case_or_404(db, case_id)
    return run_matching(db, c.id, c.case_type, c.description)
