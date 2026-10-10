import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.modules.audit.service import AuditLog, verify_chain
from app.modules.privacy.retention import expired_cases, purge
from app.modules.pv.router import Pv
from app.modules.reports.final import FinalReport
from tests.test_pv import DATASET

API = "/api/v1"
needs_latex = pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex not installed")


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds").replace("+00:00", "Z")


# ------------------------------------------------------------------ right of access

def test_user_can_export_their_own_data(client, other_mandataire):
    mine = client.post(f"{API}/cases", json={"case_type": "malware", "description": "Ransomware sur le serveur de fichiers.",
                                            "priority": "basse", "mandataire": {"nom": "Dupont", "fonction": "juge"}}).json()["case_id"]
    r = client.get(f"{API}/privacy/export")
    assert r.status_code == 200 and "content-disposition" not in r.headers  # not a download as far as download managers see
    data = r.json()
    assert data["account"]["email"] == "juge.dupont@tribunal.test" and data["account"]["role"] == "mandataire"
    assert mine in [c["case_id"] for c in data["cases"]]
    assert any(a["action"] == "create_case" for a in data["activity"])
    text = json.dumps(data)
    assert "password" not in text and "$2" not in text  # no hashes, no secrets
    # another user's export never contains this user's cases
    theirs = other_mandataire.get(f"{API}/privacy/export").json()
    assert mine not in [c["case_id"] for c in theirs["cases"]]


def test_export_is_recorded_and_needs_login(client, anon):
    client.get(f"{API}/privacy/export")
    with SessionLocal() as db:
        assert db.scalars(select(AuditLog).where(AuditLog.action == "export_personal_data")).first() is not None
    assert anon.get(f"{API}/privacy/export").status_code == 401


def test_investigator_export_lists_their_requests(chosen_case):
    _, expert = chosen_case()
    data = expert.get(f"{API}/privacy/export").json()
    assert data["account"]["role"] == "investigateur" and data["requests"] and data["requests"][0]["status"] == "chosen"
    assert "Lambert" not in json.dumps(data)  # no witness statement content in a personal export


# ------------------------------------------------------------------ retention

@pytest.fixture
def finished_case(chosen_case):
    """A mission with PVs, a technical report, a guide and a final report generated 8 months ago."""
    cid, expert = chosen_case()
    for i in (0, 1):
        pv = DATASET["pvs"][i]
        expert.post(f"{API}/pv/analyze", json={"case_id": cid, "pv_id": pv["pv_id"], "pv_text": pv["text"], "witness_name": pv["witness"]})
    expert.post(f"{API}/mission/prepare", json={"case_id": cid})
    expert.post(f"{API}/reports/analyze", json={"case_id": cid, "rapports": [
        {"rapport_id": "r1", "action": "analyse_logs", "outils": ["Splunk"], "resultats": "journaux", "preuves": ["a.txt"]}]})
    return cid, expert


def _age_report(cid: str, days: float):
    with SessionLocal() as db:
        for r in db.scalars(select(FinalReport).where(FinalReport.case_id == cid)):
            r.generated_at = _iso(days)
        db.commit()


@needs_latex
def test_dry_run_changes_nothing_and_apply_deletes_interview_data_only(finished_case):
    cid, expert = finished_case
    assert expert.post(f"{API}/reports/generate", json={"case_id": cid}).status_code == 201
    pv_dir = Path(os.environ["OUTPUT_DIR"]) / "pv" / cid
    guide_dir = Path(os.environ["OUTPUT_DIR"]) / "guides" / cid
    assert pv_dir.exists() and guide_dir.exists()

    with SessionLocal() as db:
        assert cid not in [c.case_id for c in expired_cases(db, 6)]  # report is brand new: kept
    _age_report(cid, 8 * 31)

    with SessionLocal() as db:
        found = {c.case_id: c for c in purge(db, 6, apply=False)}
        assert found[cid].pvs == 2 and found[cid].tech_reports == 1
    assert pv_dir.exists() and guide_dir.exists()  # dry run: untouched
    assert len(expert.get(f"{API}/pv?case_id={cid}").json()["pvs"]) == 2

    with SessionLocal() as db:
        purge(db, 6, apply=True)
        assert db.scalars(select(Pv).where(Pv.case_id == cid)).first() is None
        assert db.scalars(select(FinalReport).where(FinalReport.case_id == cid)).first() is not None  # deliverable stays
        entry = db.scalars(select(AuditLog).where(AuditLog.action == "retention_purge", AuditLog.case_id == cid)).one()
        assert entry.payload["pvs_deleted"] == 2 and entry.user == "system"
        assert verify_chain(db)["valid"] is True  # the chain of custody survives the purge
    assert not pv_dir.exists() and not guide_dir.exists()
    assert expert.get(f"{API}/pv?case_id={cid}").json()["pvs"] == []
    assert expert.get(f"{API}/reports/analysis?case_id={cid}").json()["rapports"] == []
    with SessionLocal() as db:
        assert purge(db, 6, apply=True) == []  # nothing left: idempotent


def test_unfinished_missions_are_never_purged(finished_case):
    cid, _ = finished_case  # has PVs but no final report
    with SessionLocal() as db:
        assert cid not in [c.case_id for c in purge(db, 0, apply=False)]
