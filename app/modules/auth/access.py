"""Who may see or change which case.

- mandataire: only the cases they created.
- investigateur: only cases where their expert profile was solicited or is the chosen expert.

A case the user may not access is answered with 404, not 403, so ids cannot be probed.
Routers resolve the role first (require_role), so these helpers only deal with ownership.
"""
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.auth.service import User


def _not_found() -> HTTPException:
    return HTTPException(404, "Case not found")


def _solicited(db: Session, case_id: str, expert_id: int) -> bool:
    from app.modules.workflow.router import Solicitation
    return db.scalars(select(Solicitation.id).where(
        Solicitation.case_id == case_id, Solicitation.expert_id == expert_id)).first() is not None


def case_for(db: Session, case_id: str, user: User, mode: str = "view"):
    """Load a case the user may access.

    mode "own":     the mandataire who created it
    mode "mission": the investigator who is the chosen expert
    mode "view":    owner, chosen expert, or an expert solicited for it
    """
    from app.modules.cases.router import Case
    case = db.get(Case, case_id)
    if case is None:
        raise _not_found()
    is_owner = user.role == "mandataire" and case.owner_id == user.id
    is_chosen = user.role == "investigateur" and user.expert_id is not None \
        and case.chosen_expert_id == user.expert_id
    allowed = {"own": is_owner, "mission": is_chosen}.get(mode)
    if allowed is None:  # view
        allowed = is_owner or is_chosen or (
            user.role == "investigateur" and user.expert_id is not None
            and _solicited(db, case.id, user.expert_id))
    if not allowed:
        raise _not_found()
    return case


def visible_cases(user: User):
    """SQLAlchemy WHERE clause selecting the cases a user may list."""
    from app.modules.cases.router import Case
    from app.modules.workflow.router import Solicitation
    if user.role == "mandataire":
        return Case.owner_id == user.id
    if user.expert_id is None:
        return Case.id == "-"  # an investigator account without an expert profile sees nothing
    return or_(Case.chosen_expert_id == user.expert_id,
               Case.id.in_(select(Solicitation.case_id).where(Solicitation.expert_id == user.expert_id)))


def safe_output_path(path: str, root: Path) -> Path:
    """Resolve a user-supplied file path and refuse anything outside the output directory."""
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise HTTPException(400, "file_path must be inside the output directory")
    if not resolved.is_file():
        raise HTTPException(400, "file_path does not exist")
    return resolved
