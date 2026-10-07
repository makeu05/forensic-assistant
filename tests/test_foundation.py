from sqlalchemy import update

from app.db import SessionLocal
from app.modules.audit.service import AuditLog, verify_chain
from tests.conftest import MANDAT_FRAUDE


def test_health(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_create_case_validates(client):
    bad = {**MANDAT_FRAUDE, "case_type": "inconnu"}
    assert client.post("/api/v1/cases", json=bad).status_code == 422


def test_case_to_top3_experts(client):
    r = client.post("/api/v1/cases", json=MANDAT_FRAUDE)
    assert r.status_code == 201
    cid = r.json()["case_id"]
    assert client.get(f"/api/v1/cases/{cid}").json()["status"] == "en_attente"

    experts = client.get(f"/api/v1/cases/{cid}/experts").json()["experts"]
    assert len(experts) == 3
    scores = [e["score"] for e in experts]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 1 for s in scores)
    assert all(e["justification"] for e in experts)
    # fraud case should surface a banking-fraud specialist first
    assert "forensic_bancaire" in experts[0]["competences"]


def test_unknown_case_404(client):
    assert client.get("/api/v1/cases/nope").status_code == 404


def test_audit_trail_and_chain(client):
    r = client.post("/api/v1/cases", json=MANDAT_FRAUDE)
    cid = r.json()["case_id"]
    logs = client.get(f"/api/v1/audit/logs?case_id={cid}").json()
    assert logs["total"] == 1 and logs["logs"][0]["action"] == "create_case"
    assert client.get("/api/v1/audit/chain/verify").json()["valid"] is True


def test_file_hash_verify(client, tmp_path):
    f = tmp_path / "pv.txt"
    f.write_text("declaration")
    h = client.post("/api/v1/audit/log", json={"module": "F", "action": "x", "file_path": str(f)}).json()["hash"]
    ok = client.post("/api/v1/audit/verify", json={"file_path": str(f), "expected_hash": h})
    assert ok.status_code == 200
    f.write_text("tampered")
    bad = client.post("/api/v1/audit/verify", json={"file_path": str(f), "expected_hash": h})
    assert bad.status_code == 400


def test_chain_detects_tampering(client):
    client.post("/api/v1/cases", json=MANDAT_FRAUDE)
    with SessionLocal() as db:
        original = db.get(AuditLog, 1).action
        db.execute(update(AuditLog).where(AuditLog.id == 1).values(action="forged"))
        db.commit()
        try:
            assert verify_chain(db)["valid"] is False
        finally:  # the DB is shared by the whole test session: leave the chain intact
            db.execute(update(AuditLog).where(AuditLog.id == 1).values(action=original))
            db.commit()
        assert verify_chain(db)["valid"] is True
