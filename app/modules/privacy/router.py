"""RGPD right of access: a user can download everything Locard holds about them."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.audit.service import AuditLog, log_action
from app.modules.auth.access import visible_cases
from app.modules.auth.router import current_user
from app.modules.auth.service import User
from app.modules.cases.router import Case
from app.modules.workflow.router import Solicitation

router = APIRouter(prefix="/privacy", tags=["RGPD"])

MAX_ACTIVITY = 5000


@router.get("/export")
def export_my_data(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The user's account, the cases they can access, the requests addressed to them and their own recorded
    actions, as one JSON file. Other people's data (witness statements, other users) is not included."""
    cases = db.scalars(select(Case).where(visible_cases(user)).order_by(Case.created_at)).all()
    sols = []
    if user.expert_id is not None:
        sols = db.scalars(select(Solicitation).where(Solicitation.expert_id == user.expert_id)).all()
    activity = db.scalars(select(AuditLog).where(AuditLog.user == user.email).order_by(AuditLog.id).limit(MAX_ACTIVITY)).all()
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "account": {"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role,
                    "expert_id": user.expert_id, "created_at": user.created_at},
        "cases": [{"case_id": c.id, "case_type": c.case_type, "description": c.description, "priority": c.priority,
                   "status": c.status, "created_at": c.created_at,
                   "mandataire": {"nom": c.mandataire_nom, "fonction": c.mandataire_fonction}} for c in cases],
        "requests": [{"case_id": s.case_id, "status": s.status, "reason": s.reason, "responded_at": s.responded_at} for s in sols],
        "activity": [{"timestamp": a.timestamp, "module": a.module, "action": a.action, "case_id": a.case_id} for a in activity],
        "note": "Witness statements and other people's data are not part of this export.",
    }
    log_action(db, "RGPD", "export_personal_data", user=user.email)
    return JSONResponse(data)  # no "attachment" header: download managers would swallow it; the app saves it itself
