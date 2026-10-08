import pytest

from app.core.security import RateLimiter, limiter

API = "/api/v1"


def test_limiter_blocks_after_the_limit_and_tells_how_long_to_wait():
    lim = RateLimiter()
    assert [lim.check("k", 3, now=0.0 + i) for i in range(3)] == [0, 0, 0]
    wait = lim.check("k", 3, now=3.0)
    assert 55 <= wait <= 61
    assert lim.check("other", 3, now=3.0) == 0  # buckets are independent


def test_limiter_window_slides():
    lim = RateLimiter()
    for i in range(3):
        lim.check("k", 3, now=float(i))
    assert lim.check("k", 3, now=30.0) > 0
    assert lim.check("k", 3, now=61.0) == 0  # the first hit has left the window


def test_api_answers_429_with_retry_after(raw, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "4")
    headers = {"Authorization": "Bearer bucket-for-this-test-only"}
    codes = [raw.get(f"{API}/cases", headers=headers).status_code for _ in range(6)]
    assert codes[:4] == [401] * 4 and codes[4:] == [429, 429]  # 401: fake token, but still counted
    blocked = raw.get(f"{API}/cases", headers=headers)
    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) >= 1
    assert blocked.headers["x-content-type-options"] == "nosniff"
    # another caller is not affected
    assert raw.get(f"{API}/cases", headers={"Authorization": "Bearer someone-else"}).status_code == 401


def test_login_has_its_own_stricter_limit(raw, monkeypatch):
    limiter._hits.clear()  # earlier tests already logged in from this same address
    monkeypatch.setenv("LOGIN_LIMIT_PER_MIN", "3")
    body = {"email": "nobody-rate@tribunal.test", "password": "wrong-password-123"}
    codes = [raw.post(f"{API}/auth/login", json=body).status_code for _ in range(5)]
    assert codes[:3] == [401] * 3 and codes[3:] == [429, 429]


def test_health_is_never_limited(raw, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "1")
    assert all(raw.get(f"{API}/health").status_code == 200 for _ in range(5))


def test_security_headers_on_every_api_answer(raw):
    r = raw.get(f"{API}/health")
    assert r.headers["x-frame-options"] == "DENY" and r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert "strict-transport-security" not in r.headers  # plain http in tests: HSTS only over https


def test_hsts_is_sent_over_https(raw):
    r = raw.get("https://testserver/api/v1/health")
    assert "max-age" in r.headers["strict-transport-security"]


def test_swagger_docs_keep_working(raw):
    r = raw.get("/docs")
    assert r.status_code == 200 and "content-security-policy" not in r.headers  # CSP would block its scripts


# ------------------------------------------------------------ audit log rotation (module J)

def test_audit_log_rotates_into_a_hashed_gzip_archive(tmp_path, monkeypatch):
    import gzip
    import json

    from app.modules.audit.service import rotate_log, sha256_file

    log = tmp_path / "audit.jsonl"
    lines = [json.dumps({"n": i, "action": "x" * 40}) for i in range(30)]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert rotate_log(log, max_bytes=10_000_000) is None  # below the limit: untouched
    archive = rotate_log(log, max_bytes=100)
    assert archive and archive.suffix == ".gz" and not (tmp_path / "audit.jsonl.rotating").exists()
    assert gzip.open(archive, "rt", encoding="utf-8").read().splitlines() == lines  # nothing lost
    marker = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert marker["event"] == "log_rotated" and marker["archive"] == archive.name
    assert marker["archive_sha256"] == sha256_file(str(archive))


def test_log_action_rotates_by_itself_and_never_loses_an_entry(client, tmp_path, monkeypatch):
    import gzip

    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("AUDIT_LOG_MAX_MB", "0.001")  # about 1 KB
    desc = {"case_type": "malware", "description": "Ransomware sur le serveur de fichiers.", "priority": "basse",
            "mandataire": {"nom": "Dupont", "fonction": "juge"}}
    for _ in range(12):
        assert client.post(f"{API}/cases", json=desc).status_code == 201
    archives = sorted(tmp_path.glob("audit-*.jsonl.gz"))
    assert archives, "the file should have rotated at least once"
    total = sum(len([ln for ln in gzip.open(a, "rt", encoding="utf-8").read().splitlines() if '"create_case"' in ln])
                for a in archives)
    total += len([ln for ln in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines() if '"create_case"' in ln])
    assert total == 12
