"""Invitations: how an expert who agreed to join Locard gets an account.

A mandataire solicits an expert. If that expert has no account yet, Locard emails a personal,
single-use link (7 days). The expert opens it, chooses a password, and the account is created
with the email address of the expert profile, so nobody can attach an account to another
person's profile. Only a hash of the token is stored; the token itself exists only in the email.
"""
import hashlib
import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import Boolean, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base
from app.modules.auth import service
from app.modules.auth.service import User
from app.modules.matching.service import Expert

INVITATION_TTL = timedelta(days=7)
INVALID = "Invalid or expired invitation"


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expert_id: Mapped[int] = mapped_column(Integer, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[str] = mapped_column(String(40))
    expires_at: Mapped[str] = mapped_column(String(40))
    used: Mapped[bool] = mapped_column(Boolean, default=False)  # also set when superseded by a newer link


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def user_for_expert(db: Session, expert_id: int) -> User | None:
    return db.scalars(select(User).where(User.expert_id == expert_id)).first()


def create_invitation(db: Session, expert_id: int) -> str:
    """Issue a new link and retire any earlier unused one. Returns the raw token (for the email only)."""
    for old in db.scalars(select(Invitation).where(Invitation.expert_id == expert_id, Invitation.used.is_(False))):
        old.used = True
    token = secrets.token_urlsafe(32)
    db.add(Invitation(expert_id=expert_id, token_hash=_hash(token), created_at=service.iso(service.now()),
                      expires_at=service.iso(service.now() + INVITATION_TTL)))
    db.commit()
    return token


def resolve(db: Session, token: str) -> tuple[Invitation, Expert]:
    """The valid invitation and its expert, or 404. One message for every failure reason."""
    inv = db.scalars(select(Invitation).where(Invitation.token_hash == _hash(token))).first()
    if inv is None or inv.used or service.parse(inv.expires_at) < service.now():
        raise HTTPException(404, INVALID)
    expert = db.get(Expert, inv.expert_id)
    if expert is None:
        raise HTTPException(404, INVALID)
    return inv, expert


def activate(db: Session, token: str, password: str, display_name: str | None) -> User:
    inv, expert = resolve(db, token)
    if user_for_expert(db, expert.id) or service.get_user_by_email(db, expert.email):
        raise HTTPException(409, "An account already exists for this expert")
    user = service.create_user(db, expert.email, (display_name or expert.nom), password, "investigateur", expert.id)
    inv.used = True
    db.commit()
    return user
