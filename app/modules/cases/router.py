"""Module A backend: mandate (case) creation and tracking."""
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text
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


@router.get("/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    return serialize(get_case_or_404(db, case_id))


@router.get("/{case_id}/experts")
def case_experts(case_id: str, db: Session = Depends(get_db)):
    c = get_case_or_404(db, case_id)
    return run_matching(db, c.id, c.case_type, c.description)
