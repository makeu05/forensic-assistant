import email
import os
import re
import time
from pathlib import Path

import jwt

from app.db import SessionLocal
from app.modules.auth import service
from app.modules.auth.invitations import Invitation
from tests.conftest import MANDAT_FRAUDE, PASSWORD, Api

API = "/api/v1"


def _register(raw, address, password=PASSWORD):
    return raw.post(f"{API}/auth/register", json={"email": address, "display_name": "Test User", "password": password})


def _login(raw, address, password=PASSWORD):
    return raw.post(f"{API}/auth/login", json={"email": address, "password": password})


def _outbox() -> list:
    folder = Path(os.environ["OUTPUT_DIR"]) / "outbox"
    return [email.message_from_bytes(p.read_bytes()) for p in sorted(folder.glob("*.eml"))] if folder.exists() else []


def _mails_to(address: str) -> list:
    return [m for m in _outbox() if m["To"] == address]


def _body(msg) -> str:
    return msg.get_payload(decode=True).decode()


# ------------------------------------------------------------- who may call what

def test_health_is_public_everything_else_needs_a_token(anon):
    assert anon.get(f"{API}/health").status_code == 200
    for method, url in (("get", "/cases"), ("post", "/cases"), ("get", "/pv/missions"), ("get", "/audit/chain/verify"),
                        ("get", "/solicitations/mine"), ("get", "/auth/me")):
        r = getattr(anon, method)(API + url)
        assert r.status_code == 401, url
        assert r.headers["www-authenticate"] == "Bearer"


def test_register_validation_and_duplicates(raw):
    assert _register(raw, "short@pw.test", "tooshort").status_code == 422
    assert _register(raw, "not-an-email").status_code == 422
    assert _register(raw, "new.user@tribunal.test").status_code == 201
    assert _register(raw, "NEW.USER@tribunal.test").status_code == 409  # emails are case-insensitive


def test_expert_email_cannot_be_claimed_as_a_mandataire(raw):
    from app.modules.matching.service import Expert
    with SessionLocal() as db:
        address = db.get(Expert, 30).email
    assert _register(raw, address).status_code == 409


def test_login_wrong_password_and_unknown_email_look_the_same(raw):
    _register(raw, "same.msg@tribunal.test")
    bad_pw = _login(raw, "same.msg@tribunal.test", "wrong-password-123")
    unknown = _login(raw, "nobody@tribunal.test")
    assert bad_pw.status_code == unknown.status_code == 401
    assert bad_pw.json() == unknown.json()


def test_login_and_me(raw):
    _register(raw, "me@tribunal.test")
    r = _login(raw, "me@tribunal.test")
    assert r.status_code == 200 and r.json()["expires_in"] == 3600
    me = Api(raw, r.json()["access_token"]).get(f"{API}/auth/me").json()
    assert me["email"] == "me@tribunal.test" and me["role"] == "mandataire"
    assert "password" not in str(me)


def test_account_locks_after_five_failures(raw):
    _register(raw, "lock@tribunal.test")
    for _ in range(5):
        assert _login(raw, "lock@tribunal.test", "wrong-password-123").status_code == 401
    assert _login(raw, "lock@tribunal.test").status_code == 429  # even the right password is refused


def test_bad_tokens_are_rejected(raw, client):
    secret = service._secret()
    now = int(time.time())
    base = {"sub": "1", "role": "mandataire", "typ": "access", "jti": "x", "iat": now, "exp": now + 600}
    cases = {
        "expired": jwt.encode({**base, "exp": now - 10}, secret, algorithm="HS256"),
        "wrong secret": jwt.encode(base, "another-secret-another-secret-123456", algorithm="HS256"),
        "alg none": jwt.encode(base, None, algorithm="none"),
        "refresh used as access": jwt.encode({**base, "typ": "refresh"}, secret, algorithm="HS256"),
        "garbage": "not.a.jwt",
    }
    for name, token in cases.items():
        assert Api(raw, token).get(f"{API}/cases").status_code == 401, name
    # a valid token whose payload was edited after signing
    head, payload, sig = client.token.split(".")
    assert Api(raw, f"{head}.{payload[:-2]}AA.{sig}").get(f"{API}/cases").status_code == 401


def test_refresh_rotates_and_reuse_revokes_everything(raw):
    first = _register(raw, "rotate@tribunal.test").json()
    second = raw.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    assert Api(raw, second.json()["access_token"]).get(f"{API}/auth/me").status_code == 200
    # the first refresh token was used: presenting it again means theft, so the new one dies too
    assert raw.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    assert raw.post(f"{API}/auth/refresh", json={"refresh_token": second.json()["refresh_token"]}).status_code == 401


def test_logout_revokes_the_refresh_token(raw):
    tokens = _register(raw, "bye@tribunal.test").json()
    assert raw.post(f"{API}/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code == 204
    assert raw.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_access_token_cannot_be_used_to_refresh(raw):
    tokens = _register(raw, "typed@tribunal.test").json()
    assert raw.post(f"{API}/auth/refresh", json={"refresh_token": tokens["access_token"]}).status_code == 401


def test_passwords_are_stored_hashed(raw):
    _register(raw, "hashed@tribunal.test")
    with SessionLocal() as db:
        stored = service.get_user_by_email(db, "hashed@tribunal.test").password_hash
    assert stored.startswith("$2") and PASSWORD not in stored


# ---------------------------------------------------------------- roles and ownership

def test_roles_are_enforced(client, expert_api, chosen_case):
    cid, expert = chosen_case()
    assert client.get(f"{API}/pv/missions").status_code == 403  # a mandataire is not an investigator
    assert client.post(f"{API}/pv/analyze", json={"case_id": cid, "pv_id": "p1", "pv_text": "x" * 30,
                                                  "witness_name": "Test Test"}).status_code == 403
    assert expert.post(f"{API}/cases", json=MANDAT_FRAUDE).status_code == 403  # nor the reverse
    assert expert.post(f"{API}/contracts/generate", json={"case_id": cid}).status_code == 403


def test_a_mandataire_only_sees_their_own_cases(client, other_mandataire):
    cid = client.post(f"{API}/cases", json=MANDAT_FRAUDE).json()["case_id"]
    assert other_mandataire.get(f"{API}/cases/{cid}").status_code == 404  # 404, not 403: the id is not confirmed
    assert cid not in [c["case_id"] for c in other_mandataire.get(f"{API}/cases").json()["cases"]]
    assert cid in [c["case_id"] for c in client.get(f"{API}/cases").json()["cases"]]
    for method, url, body in (("get", f"/cases/{cid}/experts", None), ("post", f"/cases/{cid}/sign", {"signatory_name": "Intrus"}),
                              ("get", f"/audit/logs?case_id={cid}", None), ("get", f"/solicitations?case_id={cid}", None),
                              ("post", "/contracts/generate", {"case_id": cid}),
                              ("post", "/solicitations", {"case_id": cid, "expert_ids": [1]})):
        r = getattr(other_mandataire, method)(API + url, **({"json": body} if body else {}))
        assert r.status_code == 404, url


def test_an_investigator_only_sees_cases_they_are_involved_in(client, expert_api, chosen_case):
    cid, expert = chosen_case()
    outsider = expert_api(45)  # never solicited for this case
    assert outsider.get(f"{API}/cases/{cid}").status_code == 404
    assert outsider.get(f"{API}/solicitations?case_id={cid}").status_code == 404
    assert outsider.post(f"{API}/mission/prepare", json={"case_id": cid}).status_code == 404
    assert cid not in [c["case_id"] for c in outsider.get(f"{API}/cases").json()["cases"]]
    assert expert.get(f"{API}/cases/{cid}").status_code == 200


def test_only_the_solicited_expert_can_answer(client, expert_api):
    cid = client.post(f"{API}/cases", json=MANDAT_FRAUDE).json()["case_id"]
    sols = client.post(f"{API}/solicitations", json={"case_id": cid, "expert_ids": [41, 42]}).json()["solicitations"]
    sid_for_41 = sols[0]["id"]
    assert expert_api(42).put(f"{API}/solicitations/{sid_for_41}/respond", json={"status": "accepted"}).status_code == 404
    assert client.put(f"{API}/solicitations/{sid_for_41}/respond", json={"status": "accepted"}).status_code == 403
    assert expert_api(41).put(f"{API}/solicitations/{sid_for_41}/respond", json={"status": "accepted"}).status_code == 200
    # an expert sees only their own row, never who else was approached
    rows = expert_api(41).get(f"{API}/solicitations?case_id={cid}").json()["solicitations"]
    assert [r["expert_id"] for r in rows] == [41]
    mine = expert_api(42).get(f"{API}/solicitations/mine").json()["solicitations"]
    assert cid in [m["case"]["case_id"] for m in mine]


# ------------------------------------------------------------------------ audit trail

def test_audit_names_the_authenticated_user_and_ignores_a_spoofed_one(client):
    cid = client.post(f"{API}/cases", json=MANDAT_FRAUDE).json()["case_id"]
    client.post(f"{API}/audit/log", json={"module": "A", "action": "note", "case_id": cid, "user": "someone.else"})
    logs = client.get(f"{API}/audit/logs?case_id={cid}").json()["logs"]
    assert {log["user"] for log in logs} == {"juge.dupont@tribunal.test"}


def test_audit_cannot_be_used_to_read_arbitrary_files(client):
    for path in ("/etc/passwd", "C:/Windows/win.ini", "../../app/main.py", __file__):
        assert client.post(f"{API}/audit/log", json={"module": "A", "action": "x", "file_path": path}).status_code == 400
        assert client.post(f"{API}/audit/verify", json={"file_path": path, "expected_hash": "0" * 64}).status_code == 400


def test_audit_log_listing_requires_a_case(client):
    assert client.get(f"{API}/audit/logs").status_code == 422


def test_audit_records_logins_but_never_tokens_or_passwords(raw, client):
    _register(raw, "audited@tribunal.test")
    log_text = Path(os.environ["AUDIT_LOG_PATH"]).read_text(encoding="utf-8")
    assert '"action": "register"' in log_text and "audited@tribunal.test" in log_text
    assert PASSWORD not in log_text and "eyJ" not in log_text


# ------------------------------------------------------- invitation emails for experts

def _solicit(client, expert_ids):
    cid = client.post(f"{API}/cases", json=MANDAT_FRAUDE).json()["case_id"]
    r = client.post(f"{API}/solicitations", json={"case_id": cid, "expert_ids": expert_ids})
    assert r.status_code == 201
    return cid


def _expert_email(expert_id: int) -> str:
    from app.modules.matching.service import Expert
    with SessionLocal() as db:
        return db.get(Expert, expert_id).email


def _token_from(msg) -> str:
    return re.search(r"/activate\?token=([A-Za-z0-9_-]+)", _body(msg)).group(1)


def test_solicited_expert_without_account_gets_an_invitation_email(client):
    address = _expert_email(50)
    assert _mails_to(address) == []
    _solicit(client, [50])
    mails = _mails_to(address)
    assert len(mails) == 1
    mail = mails[0]
    assert mail["Subject"].startswith("Locard") and "From" in mail
    body = _body(mail)
    assert "http://locard.test/activate?token=" in body
    assert "fraude_bancaire" in body
    assert MANDAT_FRAUDE["description"][:25] not in body  # case details stay out of the email


def test_expert_activates_the_account_from_the_email(raw, client):
    address = _expert_email(51)
    _solicit(client, [51])
    token = _token_from(_mails_to(address)[0])

    info = raw.get(f"{API}/auth/invitation", params={"token": token}).json()
    assert info["email"] == address

    assert raw.post(f"{API}/auth/activate", json={"token": token, "password": "short"}).status_code == 422
    r = raw.post(f"{API}/auth/activate", json={"token": token, "password": PASSWORD})
    assert r.status_code == 201
    user = r.json()["user"]
    assert user["role"] == "investigateur" and user["expert_id"] == 51 and user["email"] == address
    assert Api(raw, r.json()["access_token"]).get(f"{API}/pv/missions").status_code == 200
    assert _login(raw, address).status_code == 200

    welcome = [m for m in _mails_to(address) if "actif" in m["Subject"]]
    assert len(welcome) == 1 and "confirmée" in _body(welcome[0])

    # the link works once only
    assert raw.post(f"{API}/auth/activate", json={"token": token, "password": PASSWORD}).status_code == 404
    assert raw.get(f"{API}/auth/invitation", params={"token": token}).status_code == 404


def test_expert_with_an_account_gets_a_notice_not_an_invitation(client, expert_api):
    expert_api(52)
    address = _expert_email(52)
    _solicit(client, [52])
    last = _mails_to(address)[-1]
    assert "nouvelle demande" in last["Subject"] and "activate" not in _body(last)


def test_a_new_invitation_replaces_the_previous_link(raw, client):
    address = _expert_email(53)
    _solicit(client, [53])
    _solicit(client, [53])
    old, new = (_token_from(m) for m in _mails_to(address))
    assert raw.get(f"{API}/auth/invitation", params={"token": old}).status_code == 404
    assert raw.get(f"{API}/auth/invitation", params={"token": new}).status_code == 200


def test_expired_and_forged_invitations_are_refused(raw, client):
    address = _expert_email(54)
    _solicit(client, [54])
    token = _token_from(_mails_to(address)[0])
    with SessionLocal() as db:
        inv = db.query(Invitation).filter(Invitation.expert_id == 54, Invitation.used.is_(False)).one()
        inv.expires_at = "2020-01-01T00:00:00Z"
        db.commit()
    assert raw.post(f"{API}/auth/activate", json={"token": token, "password": PASSWORD}).status_code == 404
    assert raw.post(f"{API}/auth/activate", json={"token": "x" * 43, "password": PASSWORD}).status_code == 404


def test_invitation_token_is_stored_hashed(client):
    address = _expert_email(55)
    _solicit(client, [55])
    token = _token_from(_mails_to(address)[0])
    with SessionLocal() as db:
        stored = [i.token_hash for i in db.query(Invitation).filter(Invitation.expert_id == 55)]
    assert token not in stored and all(len(h) == 64 for h in stored)
    log_text = Path(os.environ["AUDIT_LOG_PATH"]).read_text(encoding="utf-8")
    assert token not in log_text  # the audit trail records the invitation, never the secret link


def test_mail_failure_does_not_break_the_request(client, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", "1")  # nothing listens here
    cid = client.post(f"{API}/cases", json=MANDAT_FRAUDE).json()["case_id"]
    assert client.post(f"{API}/solicitations", json={"case_id": cid, "expert_ids": [56]}).status_code == 201
