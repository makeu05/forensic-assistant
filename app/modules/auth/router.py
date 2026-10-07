"""Authentication endpoints and the FastAPI dependencies used by every other module."""
import re

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.mail import send_email, welcome_mail
from app.db import get_db
from app.modules.audit.service import log_action
from app.modules.auth import invitations, service
from app.modules.auth.service import User
from app.modules.matching.service import Expert

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer = HTTPBearer(auto_error=False)

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
UNAUTHORIZED = {"WWW-Authenticate": "Bearer"}


def _email(value: str) -> str:
    value = value.strip().lower()
    if not EMAIL_RE.match(value):
        raise ValueError("invalid email address")
    return value


class RegisterIn(BaseModel):
    email: str
    display_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return _email(value)


class ActivateIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=12, max_length=128)
    display_name: str | None = Field(default=None, min_length=2, max_length=100)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                 db: Session = Depends(get_db)) -> User:
    """Resolve the bearer access token to a user, or answer 401."""
    if creds is None:
        raise HTTPException(401, "Authentication required", headers=UNAUTHORIZED)
    try:
        claims = service.decode_token(creds.credentials, "access")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token", headers=UNAUTHORIZED) from None
    user = db.get(User, int(claims["sub"]))
    if user is None:
        raise HTTPException(401, "Invalid or expired token", headers=UNAUTHORIZED)
    return user


def require_role(*roles: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "This action is not available for your role")
        return user
    return dependency


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """Self-service sign-up is for mandataires only. Investigator accounts are created by an administrator."""
    reserved = db.scalars(select(Expert.id).where(Expert.email == body.email)).first() is not None
    if reserved or service.get_user_by_email(db, body.email):
        raise HTTPException(409, "An account with this email already exists")
    user = service.create_user(db, body.email, body.display_name, body.password, "mandataire")
    log_action(db, "AUTH", "register", user=user.email, data={"role": user.role})
    return {**service.issue_pair(db, user), "user": service.serialize(user)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = service.get_user_by_email(db, body.email)
    if user is None:
        service.burn_password_check(body.password)
        raise HTTPException(401, "Invalid email or password")
    if user.locked_until and service.parse(user.locked_until) > service.now():
        raise HTTPException(429, "Too many failed attempts: try again later")
    if not service.verify_password(body.password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= service.MAX_FAILED_LOGINS:
            user.failed_attempts = 0
            user.locked_until = service.iso(service.now() + service.LOCK_DURATION)
            db.commit()
            log_action(db, "AUTH", "account_locked", user=user.email)
        else:
            db.commit()
        raise HTTPException(401, "Invalid email or password")
    user.failed_attempts, user.locked_until = 0, None
    db.commit()
    log_action(db, "AUTH", "login", user=user.email)
    return {**service.issue_pair(db, user), "user": service.serialize(user)}


@router.post("/refresh")
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    try:
        claims = service.decode_token(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token", headers=UNAUTHORIZED) from None
    stored = db.get(service.RefreshToken, claims["jti"])
    user = db.get(User, int(claims["sub"]))
    if stored is None or user is None:
        raise HTTPException(401, "Invalid or expired token", headers=UNAUTHORIZED)
    if stored.revoked:
        service.revoke_all(db, user.id)  # a used token came back: assume theft, end every session
        log_action(db, "AUTH", "refresh_reuse_detected", user=user.email)
        raise HTTPException(401, "Invalid or expired token", headers=UNAUTHORIZED)
    stored.revoked = True
    db.commit()
    return {**service.issue_pair(db, user), "user": service.serialize(user)}


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    try:
        claims = service.decode_token(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        return  # nothing to revoke
    stored = db.get(service.RefreshToken, claims["jti"])
    if stored:
        stored.revoked = True
        db.commit()


@router.get("/me")
def me(user: User = Depends(current_user)):
    return service.serialize(user)


@router.get("/invitation")
def invitation(token: str, db: Session = Depends(get_db)):
    """What the activation page needs to greet the expert. Reveals nothing for a bad token."""
    _, expert = invitations.resolve(db, token)
    return {"expert_name": expert.nom, "email": expert.email}


@router.post("/activate", status_code=201)
def activate(body: ActivateIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    """An invited expert chooses a password. The account takes the email of the expert profile."""
    user = invitations.activate(db, body.token, body.password, body.display_name)
    log_action(db, "AUTH", "activate_account", user=user.email, data={"expert_id": user.expert_id})
    subject, text = welcome_mail(user.display_name, user.email)
    background.add_task(send_email, user.email, subject, text)
    return {**service.issue_pair(db, user), "user": service.serialize(user)}
