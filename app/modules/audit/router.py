import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.audit import service
from app.modules.audit.service import AuditLog

router = APIRouter(prefix="/audit", tags=["J - Audit"])


class LogIn(BaseModel):
    module: str
    action: str
    case_id: str | None = None
    user: str | None = None
    data: dict = {}
    file_path: str | None = None


class VerifyIn(BaseModel):
    file_path: str
    expected_hash: str


@router.post("/log", status_code=201)
def create_log(body: LogIn, db: Session = Depends(get_db)):
    if body.file_path and not os.path.isfile(body.file_path):
        raise HTTPException(400, "file_path does not exist")
    e = service.log_action(db, body.module, body.action, body.case_id, body.user, body.data, body.file_path)
    return {"logged": True, "timestamp": e.timestamp, "hash": e.file_hash, "entry_hash": e.entry_hash}


@router.post("/verify")
def verify(body: VerifyIn):
    if not os.path.isfile(body.file_path):
        raise HTTPException(400, "file_path does not exist")
    if not service.verify_file(body.file_path, body.expected_hash):
        raise HTTPException(400, "Hash mismatch: file integrity compromised")
    return {"valid": True, "message": "Hash verified successfully"}


@router.get("/logs")
def list_logs(case_id: str | None = None, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    limit = min(limit, 50)
    q = select(AuditLog)
    cq = select(func.count()).select_from(AuditLog)
    if case_id:
        q, cq = q.where(AuditLog.case_id == case_id), cq.where(AuditLog.case_id == case_id)
    rows = db.scalars(q.order_by(AuditLog.id).limit(limit).offset(offset)).all()
    return {
        "case_id": case_id,
        "total": db.scalar(cq),
        "logs": [
            {
                "id": r.id, "timestamp": r.timestamp, "module": r.module, "action": r.action,
                "case_id": r.case_id, "user": r.user, "payload": r.payload,
                "file_path": r.file_path, "hash": r.file_hash, "entry_hash": r.entry_hash,
            }
            for r in rows
        ],
    }


@router.get("/chain/verify")
def verify_chain(db: Session = Depends(get_db)):
    return service.verify_chain(db)
