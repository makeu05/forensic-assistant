"""RGPD retention: personal data from interviews is deleted some months after the mission ends.

A mission ends when its final report exists. Six months after the most recent report, the personal
content gathered during the mission is deleted:
  - the PV texts (the case's folder of files) and their analysis (rows): they hold witnesses' names and statements,
  - the technical reports (rows),
  - the interview guides (files).
What stays: the contract and the final report (the mission's deliverables, kept for the mandataire),
and the whole audit trail. The audit trail records who did what and when, never statement content, and
its hash chain must stay intact for the chain of custody. The purge itself is written to it.

Dry run by default: nothing is deleted unless apply=True.
"""
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.audit.service import log_action
from app.modules.contracts.router import output_dir
from app.modules.pv.router import Pv
from app.modules.reports.final import FinalReport
from app.modules.reports.tech import TechReport

DEFAULT_MONTHS = 6
DAYS_PER_MONTH = 30.44


@dataclass
class CasePurge:
    case_id: str
    report_at: str
    pvs: int
    tech_reports: int
    files: list[str] = field(default_factory=list)


def _cutoff(months: float, now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)) - timedelta(days=months * DAYS_PER_MONTH)


def expired_cases(db: Session, months: float = DEFAULT_MONTHS, now: datetime | None = None) -> list[CasePurge]:
    """Cases whose latest final report is older than `months`, with what would be deleted."""
    cutoff = _cutoff(months, now).isoformat(timespec="seconds").replace("+00:00", "Z")
    latest = db.execute(select(FinalReport.case_id, func.max(FinalReport.generated_at)).group_by(FinalReport.case_id)).all()
    out = []
    for case_id, report_at in latest:
        if report_at > cutoff:
            continue
        pvs = list(db.scalars(select(Pv).where(Pv.case_id == case_id)))
        n_tech = db.scalar(select(func.count()).select_from(TechReport).where(TechReport.case_id == case_id)) or 0
        folders = [output_dir() / "pv" / case_id, output_dir() / "guides" / case_id]
        files = [str(f) for f in folders if f.exists()]
        if pvs or n_tech or files:
            out.append(CasePurge(case_id, report_at, len(pvs), n_tech, files))
    return out


def purge(db: Session, months: float = DEFAULT_MONTHS, apply: bool = False, now: datetime | None = None) -> list[CasePurge]:
    """Delete the personal content of every expired case (only with apply=True). Returns what was, or would be, deleted."""
    found = expired_cases(db, months, now)
    if not apply:
        return found
    for item in found:
        for f in item.files:
            path = Path(f)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
        db.execute(delete(Pv).where(Pv.case_id == item.case_id))
        db.execute(delete(TechReport).where(TechReport.case_id == item.case_id))
        db.commit()
        log_action(db, "RGPD", "retention_purge", case_id=item.case_id, user="system",
                   data={"months": months, "pvs_deleted": item.pvs, "tech_reports_deleted": item.tech_reports})
    return found
