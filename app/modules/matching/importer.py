"""Load real expert profiles from a CSV file, and remove the demo ones.

CSV columns (a header line is required, order does not matter, `,` or `;` as separator):
  nom                  full name
  email                the address invitations are sent to; also the investigator's login
  competences          skills separated by `|`, for example  forensic_bancaire|analyse_logs
  bio                  free text, used by the matching (optional)
  annees_experience    whole number of years, 0 to 60 (optional, default 0)
  disponibilite        oui / non (also true/false, 1/0). Optional, default oui

Nothing is written unless apply=True. An address already in the base is skipped, never overwritten.
"""
import csv
import io
import re
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.matching.service import Expert

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
DEMO_DOMAIN = "@experts.example"
REQUIRED = {"nom", "email", "competences"}
TRUE = {"oui", "true", "1", "yes", "o", "vrai"}
FALSE = {"non", "false", "0", "no", "n", "faux"}


@dataclass
class ImportResult:
    rows: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # addresses already in the base


def parse_csv(text: str) -> ImportResult:
    """Validate the whole file. Every problem is reported with its line number; valid rows are kept."""
    result = ImportResult()
    text = text.lstrip("﻿")  # a BOM from Excel
    sample = text[:2000]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = {h.strip().lower() for h in (reader.fieldnames or []) if h}
    missing = REQUIRED - headers
    if missing:
        result.errors.append(f"Missing column(s): {', '.join(sorted(missing))}")
        return result
    seen: set[str] = set()
    for line, raw in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        problems = []
        if len(row["nom"]) < 2 or len(row["nom"]) > 100:
            problems.append("nom must be 2 to 100 characters")
        email = row["email"].lower()
        if not EMAIL_RE.match(email):
            problems.append(f"invalid email '{row['email']}'")
        elif email in seen:
            problems.append(f"email {email} appears twice in the file")
        skills = [s.strip().lower().replace(" ", "_") for s in re.split(r"[|]", row["competences"]) if s.strip()]
        if not skills:
            problems.append("at least one competence is required")
        years_text = row.get("annees_experience", "") or "0"
        if not years_text.isdigit() or not 0 <= int(years_text) <= 60:
            problems.append("annees_experience must be a whole number from 0 to 60")
        available = row.get("disponibilite", "").lower() or "oui"
        if available not in TRUE | FALSE:
            problems.append("disponibilite must be oui or non")
        if problems:
            result.errors.append(f"line {line}: " + "; ".join(problems))
            continue
        seen.add(email)
        result.rows.append({"nom": row["nom"], "email": email, "competences": skills, "bio": row.get("bio", ""),
                            "annees_experience": int(years_text), "disponibilite": available in TRUE})
    return result


def import_experts(db: Session, result: ImportResult, apply: bool = False) -> ImportResult:
    """Keep the rows whose address is new. With apply=True they are added to the base."""
    existing = set(db.scalars(select(func.lower(Expert.email))))
    new_rows = []
    for row in result.rows:
        if row["email"] in existing:
            result.skipped.append(row["email"])
        else:
            new_rows.append(row)
    result.rows = new_rows
    if apply:
        for row in new_rows:
            db.add(Expert(**row))
        db.commit()
    return result


def demo_experts_removable(db: Session) -> list[Expert]:
    """Demo profiles (@experts.example) that nothing refers to: no account, no solicitation."""
    from app.modules.auth.service import User
    from app.modules.workflow.router import Solicitation
    used = set(db.scalars(select(Solicitation.expert_id))) | {i for i in db.scalars(select(User.expert_id)) if i}
    demo = db.scalars(select(Expert).where(func.lower(Expert.email).like(f"%{DEMO_DOMAIN}"))).all()
    return [e for e in demo if e.id not in used]


def remove_demo_experts(db: Session, apply: bool = False) -> list[Expert]:
    removable = demo_experts_removable(db)
    if apply and removable:
        db.execute(delete(Expert).where(Expert.id.in_([e.id for e in removable])))
        db.commit()
    return removable
