from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.access import case_for
from app.modules.auth.router import require_role
from app.modules.auth.service import User
from app.modules.audit.service import log_action
from app.modules.matching.service import Expert, match_experts

router = APIRouter(prefix="/matching", tags=["B - Matching"])


class MatchIn(BaseModel):
    case_id: str
    case_type: str
    description: str


def run_matching(db: Session, case_id: str, case_type: str, description: str, actor: str | None = None) -> dict:
    experts = list(db.scalars(select(Expert)))
    top = match_experts(description, case_type, experts)
    log_action(db, "B", "match_experts", case_id=case_id, user=actor, data={"expert_ids": [e["id"] for e in top]})
    return {"case_id": case_id, "experts": top}


@router.post("/experts")
def match(body: MatchIn, user: User = Depends(require_role("mandataire")), db: Session = Depends(get_db)):
    case_for(db, body.case_id, user, "own")
    return run_matching(db, body.case_id, body.case_type, body.description, user.email)
