
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.access import case_for, safe_output_path
from app.modules.auth.router import current_user
from app.modules.auth.service import User
from app.modules.contracts.router import output_dir
from app.modules.audit import service
from app.modules.audit.service import AuditLog

router = APIRouter(prefix="/audit", tags=["J - Audit"])


class LogIn(BaseModel):
    module: str
    action: str
    case_id: str | None = None
    data: dict = {}
    file_path: str | None = None


class VerifyIn(BaseModel):
    file_path: str
    expected_hash: str


@router.post("/log", status_code=201)
def create_log(body: LogIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.case_id:
        case_for(db, body.case_id, user, "view")
    path = str(safe_output_path(body.file_path, output_dir())) if body.file_path else None
    # the acting user is always the authenticated one, never a value sent by the client
    e = service.log_action(db, body.module, body.action, body.case_id, user.email, body.data, path)
    return {"logged": True, "timestamp": e.timestamp, "hash": e.file_hash, "entry_hash": e.entry_hash}


@router.post("/verify")
def verify(body: VerifyIn, user: User = Depends(current_user)):
    path = str(safe_output_path(body.file_path, output_dir()))
    if not service.verify_file(path, body.expected_hash):
        raise HTTPException(400, "Hash mismatch: file integrity compromised")
    return {"valid": True, "message": "Hash verified successfully"}


@router.get("/logs")
def list_logs(case_id: str, module: str | None = None, actor: str | None = None, action: str | None = None,
              order: str = "asc", limit: int = 50, offset: int = 0, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    """The audit trail of one case. Filters: module, actor (part of the user's email), action (part of its name)."""
    case_for(db, case_id, user, "view")
    limit = max(1, min(limit, 50))
    conditions = [AuditLog.case_id == case_id]
    if module:
        conditions.append(AuditLog.module == module)
    if actor:
        conditions.append(AuditLog.user.ilike(f"%{actor}%"))
    if action:
        conditions.append(AuditLog.action.ilike(f"%{action}%"))
    ordering = AuditLog.id.desc() if order == "desc" else AuditLog.id
    rows = db.scalars(select(AuditLog).where(*conditions).order_by(ordering).limit(limit).offset(offset)).all()
    root = output_dir().resolve()

    def shown(path: str | None) -> str | None:  # never reveal the server's absolute paths
        if not path:
            return None
        p = Path(path).resolve()
        return str(p.relative_to(root)) if p.is_relative_to(root) else p.name

    return {
        "case_id": case_id,
        "total": db.scalar(select(func.count()).select_from(AuditLog).where(*conditions)),
        "modules": sorted(db.scalars(select(AuditLog.module).where(AuditLog.case_id == case_id).distinct())),
        "logs": [
            {
                "id": r.id, "timestamp": r.timestamp, "module": r.module, "action": r.action,
                "case_id": r.case_id, "user": r.user, "payload": r.payload, "file": shown(r.file_path),
                "hash": r.file_hash, "entry_hash": r.entry_hash, "prev_hash": r.prev_hash,
            }
            for r in rows
        ],
    }


@router.get("/chain/verify")
def verify_chain(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.verify_chain(db)
