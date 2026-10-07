"""Module D: expert acceptance workflow (state machine)."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base, get_db
from app.modules.audit.service import log_action
from app.modules.cases.router import Case, get_case_or_404
from app.modules.matching.service import Expert

router = APIRouter(prefix="/solicitations", tags=["D - Workflow"])

# pending -> accepted | refused ; accepted -> chosen
TRANSITIONS = {
    "pending": {"accepted", "refused"},
    "accepted": {"chosen"},
    "refused": set(),
    "chosen": set(),
}


class Solicitation(Base):
    __tablename__ = "solicitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    expert_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _transition(s: Solicitation, new: str) -> None:
    if new not in TRANSITIONS[s.status]:
        raise HTTPException(409, f"Invalid transition {s.status} -> {new}")
    s.status = new


def _ser(s: Solicitation) -> dict:
    return {"id": s.id, "case_id": s.case_id, "expert_id": s.expert_id, "status": s.status,
            "reason": s.reason, "responded_at": s.responded_at}


class SolicitIn(BaseModel):
    case_id: str
    expert_ids: list[int] = Field(min_length=1, max_length=3)


class RespondIn(BaseModel):
    status: Literal["accepted", "refused"]
    reason: str | None = None


class SelectIn(BaseModel):
    case_id: str
    expert_id: int


@router.post("", status_code=201)
def solicit(body: SolicitIn, db: Session = Depends(get_db)):
    get_case_or_404(db, body.case_id)
    if len(set(body.expert_ids)) != len(body.expert_ids):
        raise HTTPException(400, "Duplicate expert ids")
    for eid in body.expert_ids:
        if not db.get(Expert, eid):
            raise HTTPException(404, f"Expert {eid} not found")
    rows = [Solicitation(case_id=body.case_id, expert_id=eid) for eid in body.expert_ids]
    db.add_all(rows)
    db.commit()
    log_action(db, "D", "solicit_experts", case_id=body.case_id, data={"expert_ids": body.expert_ids})
    return {"solicitations": [_ser(r) for r in rows]}


@router.get("")
def list_solicitations(case_id: str, db: Session = Depends(get_db)):
    rows = db.scalars(select(Solicitation).where(Solicitation.case_id == case_id).order_by(Solicitation.id))
    return {"case_id": case_id, "solicitations": [_ser(r) for r in rows]}


@router.put("/{sid}/respond")
def respond(sid: int, body: RespondIn, db: Session = Depends(get_db)):
    s = db.get(Solicitation, sid)
    if not s:
        raise HTTPException(404, "Solicitation not found")
    _transition(s, body.status)
    s.reason, s.responded_at = body.reason, _now()
    db.commit()
    log_action(db, "D", f"expert_{body.status}", case_id=s.case_id,
               data={"expert_id": s.expert_id, "reason": body.reason})
    return {"id": s.id, "status": s.status, "responded_at": s.responded_at}


@router.post("/select")
def select_expert(body: SelectIn, db: Session = Depends(get_db)):
    case = get_case_or_404(db, body.case_id)
    if case.chosen_expert_id is not None:
        raise HTTPException(409, "An expert is already chosen for this case")
    s = db.scalars(select(Solicitation).where(
        Solicitation.case_id == body.case_id, Solicitation.expert_id == body.expert_id)).first()
    if not s:
        raise HTTPException(404, "Expert was not solicited for this case")
    _transition(s, "chosen")  # 409 unless the expert accepted (refused/pending cannot be chosen)
    case.chosen_expert_id, case.status = body.expert_id, "en_cours"
    db.commit()
    expert = db.get(Expert, body.expert_id)
    log_action(db, "D", "select_expert", case_id=case.id, data={"expert_id": expert.id})
    return {"chosen_expert": {"id": expert.id, "nom": expert.nom}, "selected_at": _now()}
