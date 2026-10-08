"""Module J: tamper-evident audit log (ISO/IEC 27037 chain of custody).

Every entry stores the SHA-256 of the previous entry, so editing or deleting
any past row breaks the chain and is caught by verify_chain().
"""
import gzip
import hashlib
import json
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base

GENESIS = "0" * 64
DEFAULT_MAX_MB = 100  # spec: rotate at 100 MB per file
_file_lock = threading.Lock()


def _log_path() -> Path:
    return Path(os.getenv("AUDIT_LOG_PATH", "logs/audit.jsonl"))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[str] = mapped_column(String(40))
    module: Mapped[str] = mapped_column(String(4))
    action: Mapped[str] = mapped_column(String(80))
    case_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    user: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64))


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _entry_hash(prev: str, fields: dict) -> str:
    body = json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((prev + body).encode()).hexdigest()


def _fields(e: AuditLog) -> dict:
    return {
        "timestamp": e.timestamp,
        "module": e.module,
        "action": e.action,
        "case_id": e.case_id,
        "user": e.user,
        "payload": e.payload,
        "file_path": e.file_path,
        "file_hash": e.file_hash,
    }


def log_action(
    db: Session,
    module: str,
    action: str,
    case_id: str | None = None,
    user: str | None = None,
    data: dict | None = None,
    file_path: str | None = None,
) -> AuditLog:
    """Append one entry to the audit trail (DB + JSONL file)."""
    last = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    prev = last.entry_hash if last else GENESIS

    entry = AuditLog(
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        module=module,
        action=action,
        case_id=case_id,
        user=user,
        payload=data or {},
        file_path=file_path,
        file_hash=sha256_file(file_path) if file_path else None,
        prev_hash=prev,
        entry_hash="",
    )
    entry.entry_hash = _entry_hash(prev, _fields(entry))
    db.add(entry)
    db.commit()

    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock:
        rotate_log(path, max_log_bytes())
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({**_fields(entry), "prev_hash": prev, "entry_hash": entry.entry_hash}) + "\n")
    return entry


def max_log_bytes() -> int:
    try:
        return int(float(os.getenv("AUDIT_LOG_MAX_MB", DEFAULT_MAX_MB)) * 1024 * 1024)
    except ValueError:
        return DEFAULT_MAX_MB * 1024 * 1024


def rotate_log(path: Path, max_bytes: int) -> Path | None:
    """Archive the JSONL file as .gz once it reaches max_bytes. Returns the archive, or None if not needed.

    The file is first renamed, then compressed, then the renamed copy is removed, so a crash in the middle
    never loses entries. The new file starts with a marker holding the archive name and its SHA-256, so the
    archive is itself part of the chain of custody. (The database keeps the full hash chain regardless.)
    """
    if not path.exists() or path.stat().st_size < max_bytes:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    archive, n = path.with_name(f"{path.stem}-{stamp}{path.suffix}.gz"), 1
    while archive.exists():
        archive, n = path.with_name(f"{path.stem}-{stamp}-{n}{path.suffix}.gz"), n + 1
    rotating = path.with_name(path.name + ".rotating")
    path.replace(rotating)
    with open(rotating, "rb") as src, gzip.open(archive, "wb") as dst:
        shutil.copyfileobj(src, dst)
    rotating.unlink()
    marker = {"event": "log_rotated", "archive": archive.name, "archive_sha256": sha256_file(str(archive)),
              "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
    path.write_text(json.dumps(marker) + "\n", encoding="utf-8")
    return archive


def verify_file(file_path: str, expected_hash: str) -> bool:
    return sha256_file(file_path) == expected_hash


def verify_chain(db: Session) -> dict:
    """Recompute the whole chain. Returns first broken entry id if any."""
    prev = GENESIS
    count = 0
    for e in db.scalars(select(AuditLog).order_by(AuditLog.id)):
        count += 1
        if e.prev_hash != prev or e.entry_hash != _entry_hash(prev, _fields(e)):
            return {"valid": False, "entries": count, "broken_at": e.id}
        prev = e.entry_hash
    return {"valid": True, "entries": count, "broken_at": None}
