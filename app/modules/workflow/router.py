"""Module D: expert acceptance workflow (state machine)."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.mail import base_url, invitation_mail, request_mail, send_email
from app.db import Base, get_db
from app.modules.audit.service import log_action
from app.modules.auth import invitations
from app.modules.auth.access import case_for
from app.modules.auth.router import current_user, require_role
from app.modules.auth.service import User
from app.modules.cases.router import Case
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


def _notify_experts(db: Session, background: BackgroundTasks, case: Case, expert_ids: list[int]) -> None:
    """Email each solicited expert: a sign-up link if they have no account yet, a plain notice otherwise.
    The mail never contains the case description, only its type and priority."""
    for eid in expert_ids:
        expert = db.get(Expert, eid)
        if user_acc := invitations.user_for_expert(db, eid):
            subject, text = request_mail(user_acc.display_name, case.case_type, case.priority)
            action = "notify_expert"
        else:
            token = invitations.create_invitation(db, eid)
            link = f"{base_url()}/activate?token={token}"
            subject, text = invitation_mail(expert.nom, case.case_type, case.priority, link)
            action = "invite_expert"
        background.add_task(send_email, expert.email, subject, text)
        log_action(db, "D", action, case_id=case.id, data={"expert_id": eid})  # the link is never logged


@router.post("", status_code=201)
def solicit(body: SolicitIn, background: BackgroundTasks, user: User = Depends(require_role("mandataire")),
            db: Session = Depends(get_db)):
    case = case_for(db, body.case_id, user, "own")
    if len(set(body.expert_ids)) != len(body.expert_ids):
        raise HTTPException(400, "Duplicate expert ids")
    for eid in body.expert_ids:
        if not db.get(Expert, eid):
            raise HTTPException(404, f"Expert {eid} not found")
    rows = [Solicitation(case_id=body.case_id, expert_id=eid) for eid in body.expert_ids]
    db.add_all(rows)
    db.commit()
    log_action(db, "D", "solicit_experts", case_id=body.case_id, user=user.email, data={"expert_ids": body.expert_ids})
    _notify_experts(db, background, case, body.expert_ids)
    return {"solicitations": [_ser(r) for r in rows]}


@router.get("/mine")
def my_solicitations(user: User = Depends(require_role("investigateur")), db: Session = Depends(get_db)):
    """Requests addressed to the logged-in investigator, newest first, with the case they concern."""
    if user.expert_id is None:
        return {"solicitations": []}
    rows = db.execute(select(Solicitation, Case).join(Case, Case.id == Solicitation.case_id)
                      .where(Solicitation.expert_id == user.expert_id).order_by(Solicitation.id.desc()))
    return {"solicitations": [
        {**_ser(s), "case": {"case_id": c.id, "case_type": c.case_type, "priority": c.priority,
                             "description": c.description, "created_at": c.created_at}}
        for s, c in rows]}


@router.get("")
def list_solicitations(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case_for(db, case_id, user, "view")
    query = select(Solicitation).where(Solicitation.case_id == case_id).order_by(Solicitation.id)
    if user.role == "investigateur":  # an expert never sees who else was approached
        query = query.where(Solicitation.expert_id == user.expert_id)
    rows = db.scalars(query)
    out = []
    for r in rows:
        e = db.get(Expert, r.expert_id)
        out.append({**_ser(r), "expert_nom": e.nom if e else None,
                    "expert_competences": e.competences if e else []})
    return {"case_id": case_id, "solicitations": out}


@router.put("/{sid}/respond")
def respond(sid: int, body: RespondIn, user: User = Depends(require_role("investigateur")),
            db: Session = Depends(get_db)):
    s = db.get(Solicitation, sid)
    if not s or s.expert_id != user.expert_id:  # only the solicited expert may answer
        raise HTTPException(404, "Solicitation not found")
    _transition(s, body.status)
    s.reason, s.responded_at = body.reason, _now()
    db.commit()
    log_action(db, "D", f"expert_{body.status}", case_id=s.case_id, user=user.email,
               data={"expert_id": s.expert_id, "reason": body.reason})
    return {"id": s.id, "status": s.status, "responded_at": s.responded_at}


@router.post("/select")
def select_expert(body: SelectIn, user: User = Depends(require_role("mandataire")), db: Session = Depends(get_db)):
    case = case_for(db, body.case_id, user, "own")
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
    log_action(db, "D", "select_expert", case_id=case.id, user=user.email, data={"expert_id": expert.id})
    return {"chosen_expert": {"id": expert.id, "nom": expert.nom}, "selected_at": _now()}
