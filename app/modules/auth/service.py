"""Authentication: users, bcrypt password hashing, JWT access and refresh tokens.

- Access token: 1 hour. Refresh token: 7 days, single use (rotated on every refresh).
- Presenting a refresh token that was already used revokes every session of that user
  (reuse means the token was probably stolen).
- Passwords are pre-hashed with SHA-256 before bcrypt so bcrypt's 72-byte limit never
  silently truncates a long passphrase.
"""
import base64
import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bcrypt
import jwt
from sqlalchemy import Boolean, Integer, String, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base

log = logging.getLogger("auth")

ACCESS_TTL = timedelta(hours=1)
REFRESH_TTL = timedelta(days=7)
MAX_FAILED_LOGINS = 5
LOCK_DURATION = timedelta(minutes=15)
ROLES = ("mandataire", "investigateur")
ALGORITHM = "HS256"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    expert_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)  # investigators only
    created_at: Mapped[str] = mapped_column(String(40))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[str | None] = mapped_column(String(40), nullable=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    expires_at: Mapped[str] = mapped_column(String(40))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def get_secret() -> str:
    """The signing secret. Production (LOCARD_ENV=production) refuses to run without JWT_SECRET: a random
    secret there would log everybody out at every restart and differ between server processes."""
    return _secret()


@lru_cache(maxsize=1)
def _secret() -> str:
    env = os.getenv("JWT_SECRET")
    if env:
        if len(env) < 32:
            raise RuntimeError("JWT_SECRET must be at least 32 characters")
        return env
    if os.getenv("LOCARD_ENV") == "production":
        raise RuntimeError("JWT_SECRET is required when LOCARD_ENV=production")
    log.warning("JWT_SECRET is not set: using a random secret, all sessions end when the server restarts")
    return secrets.token_urlsafe(48)


# ------------------------------------------------------------------ passwords

def _prehash(password: str) -> bytes:
    return base64.b64encode(hashlib.sha256(password.encode()).digest())


def hash_password(password: str) -> str:
    rounds = int(os.getenv("BCRYPT_ROUNDS", "12"))
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=rounds)).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(_prehash(password), hashed.encode())


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return hash_password("dummy-password-for-timing")


def burn_password_check(password: str) -> None:
    """Spend the same time as a real check so login time does not reveal whether an email exists."""
    verify_password(password, _dummy_hash())


# --------------------------------------------------------------------- tokens

def _encode(user: User, kind: str, ttl: timedelta, jti: str) -> str:
    issued = now()
    claims = {"sub": str(user.id), "role": user.role, "typ": kind, "jti": jti,
              "iat": int(issued.timestamp()), "exp": int((issued + ttl).timestamp())}
    return jwt.encode(claims, _secret(), algorithm=ALGORITHM)


def issue_pair(db: Session, user: User) -> dict:
    refresh_jti = str(uuid.uuid4())
    db.add(RefreshToken(jti=refresh_jti, user_id=user.id, expires_at=iso(now() + REFRESH_TTL)))
    db.commit()
    return {
        "access_token": _encode(user, "access", ACCESS_TTL, str(uuid.uuid4())),
        "refresh_token": _encode(user, "refresh", REFRESH_TTL, refresh_jti),
        "token_type": "bearer",
        "expires_in": int(ACCESS_TTL.total_seconds()),
    }


def decode_token(token: str, kind: str) -> dict:
    """Return the claims or raise jwt.PyJWTError. Only HS256 is accepted (no 'none' algorithm)."""
    claims = jwt.decode(token, _secret(), algorithms=[ALGORITHM],
                        options={"require": ["exp", "iat", "sub", "jti", "typ"]})
    if claims["typ"] != kind:
        raise jwt.InvalidTokenError("wrong token type")
    return claims


def revoke_all(db: Session, user_id: int) -> None:
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True))
    db.commit()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email.strip().lower())).first()


def create_user(db: Session, email: str, display_name: str, password: str, role: str,
                expert_id: int | None = None) -> User:
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    user = User(email=email.strip().lower(), display_name=display_name.strip(),
                password_hash=hash_password(password), role=role, expert_id=expert_id, created_at=iso(now()))
    db.add(user)
    db.commit()
    return user


def serialize(u: User) -> dict:
    return {"id": u.id, "email": u.email, "display_name": u.display_name, "role": u.role, "expert_id": u.expert_id}
