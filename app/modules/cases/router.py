"""Module A backend: mandate (case) creation and tracking."""
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base, get_db
from app.modules.audit.service import AuditLog, log_action
from app.modules.auth.access import case_for, visible_cases
from app.modules.auth.router import current_user, require_role
from app.modules.auth.service import User
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
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # the mandataire
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


STAGES = [("mandat", "Mandat"), ("experts", "Experts"), ("contrat", "Contrat"),
          ("preparation", "Préparation"), ("analyse", "Analyse"), ("rapport", "Rapport")]


def lifecycle(db: Session, c: Case) -> dict:
    """Where the case stands: each stage is done when its output exists, the first undone one is current."""
    from app.modules.contracts.router import Contract, output_dir
    from app.modules.pv.router import Pv
    from app.modules.reports.final import FinalReport

    def exists(model) -> bool:
        return db.scalars(select(model.id).where(model.case_id == c.id).limit(1)).first() is not None

    done = {
        "mandat": True,
        "experts": c.chosen_expert_id is not None,
        "contrat": exists(Contract),
        "preparation": (output_dir() / "guides" / c.id / "guide.pdf").is_file(),
        "analyse": exists(Pv),
        "rapport": exists(FinalReport),
    }
    current = next((k for k, _ in STAGES if not done[k]), None)
    last = db.scalar(select(func.max(AuditLog.timestamp)).where(AuditLog.case_id == c.id))
    return {
        "stages": [{"key": k, "label": label, "done": done[k], "current": k == current} for k, label in STAGES],
        "progress": round(sum(done.values()) / len(STAGES), 2),
        "last_activity": last or c.created_at,
    }


def get_case_or_404(db: Session, case_id: str) -> Case:
    c = db.get(Case, case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    return c


@router.post("", status_code=201)
def create_case(body: CaseIn, user: User = Depends(require_role("mandataire")), db: Session = Depends(get_db)):
    c = Case(
        id=str(uuid.uuid4()),
        case_type=body.case_type,
        description=body.description,
        priority=body.priority,
        mandataire_nom=body.mandataire.nom,
        mandataire_fonction=body.mandataire.fonction,
        owner_id=user.id,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    db.add(c)
    db.commit()
    log_action(db, "A", "create_case", case_id=c.id, user=user.email,
               data={"case_type": c.case_type, "priority": c.priority})
    return {"case_id": c.id}


@router.get("")
def list_cases(limit: int = 50, offset: int = 0, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    limit = max(1, min(limit, 50))
    mine = visible_cases(user)
    rows = db.scalars(select(Case).where(mine).order_by(Case.created_at.desc()).limit(limit).offset(offset)).all()
    signed = set(db.scalars(select(MandateSignature.case_id)))
    return {
        "total": db.scalar(select(func.count()).select_from(Case).where(mine)),
        "cases": [{**serialize(c), "signed": c.id in signed, **lifecycle(db, c)} for c in rows],
    }


@router.get("/{case_id}")
def get_case(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = case_for(db, case_id, user, "view")
    return {**serialize(c), "signed": is_signed(db, c.id), **lifecycle(db, c)}


@router.post("/{case_id}/sign")
def sign_mandate(case_id: str, body: SignIn, user: User = Depends(require_role("mandataire")),
                 db: Session = Depends(get_db)):
    c = case_for(db, case_id, user, "own")
    existing = db.get(MandateSignature, c.id)
    if existing:
        return {"signed": True, "signed_by": existing.signed_by, "signed_at": existing.signed_at}
    sig = MandateSignature(
        case_id=c.id, signed_by=body.signatory_name.strip(),
        signed_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    db.add(sig)
    db.commit()
    log_action(db, "A", "sign_mandate", case_id=c.id, user=user.email, data={"signed_by": sig.signed_by})
    return {"signed": True, "signed_by": sig.signed_by, "signed_at": sig.signed_at}


@router.get("/{case_id}/experts")
def case_experts(case_id: str, user: User = Depends(require_role("mandataire")), db: Session = Depends(get_db)):
    c = case_for(db, case_id, user, "own")
    return run_matching(db, c.id, c.case_type, c.description, user.email)
