import os
import tempfile

_tmp = tempfile.mkdtemp()
# TEST_DATABASE_URL runs the whole suite on another database (e.g. PostgreSQL). It must be empty.
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"
os.environ["AUDIT_LOG_PATH"] = f"{_tmp}/audit.jsonl"
os.environ["OUTPUT_DIR"] = f"{_tmp}/output"
os.environ["LOCARD_NO_DOTENV"] = "1"  # never load a developer's real .env (SMTP credentials!) in tests
os.environ["RATE_LIMIT_PER_MIN"] = "1000000"  # the suite makes hundreds of calls; limits have their own tests
os.environ["LOGIN_LIMIT_PER_MIN"] = "1000000"
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-0123456789"
os.environ["BCRYPT_ROUNDS"] = "4"  # production default is 12; 4 keeps the suite fast
os.environ["APP_BASE_URL"] = "http://locard.test"
os.environ.pop("SMTP_HOST", None)  # tests must never send real mail: mail goes to the outbox folder

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PASSWORD = "correct-horse-battery-staple"

MANDAT_FRAUDE = {
    "case_type": "fraude_bancaire",
    "description": "Virements suspects de 50000 euros vers un compte etranger, analyse des logs bancaires.",
    "priority": "haute",
    "mandataire": {"nom": "Dupont", "fonction": "juge_instruction"},
}


class Api:
    """A TestClient bound to one user's bearer token."""

    def __init__(self, raw: TestClient, token: str | None = None):
        self.raw, self.token = raw, token

    def request(self, method: str, url: str, **kw):
        headers = dict(kw.pop("headers", {}))
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return self.raw.request(method, url, headers=headers, **kw)

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)

    def put(self, url, **kw):
        return self.request("PUT", url, **kw)


@pytest.fixture(scope="session")
def raw():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def anon(raw):
    return Api(raw)


def _register(raw: TestClient, email: str) -> Api:
    r = raw.post("/api/v1/auth/register", json={"email": email, "display_name": "Mandataire Test", "password": PASSWORD})
    assert r.status_code == 201, r.text
    return Api(raw, r.json()["access_token"])


@pytest.fixture(scope="session")
def client(raw):
    """Authenticated as a mandataire (the default actor of most tests)."""
    return _register(raw, "juge.dupont@tribunal.test")


@pytest.fixture(scope="session")
def other_mandataire(raw):
    return _register(raw, "juge.autre@tribunal.test")


@pytest.fixture(scope="session")
def expert_api(raw):
    """expert_api(expert_id) -> Api logged in as the investigator account of that expert (created on demand)."""
    from app.db import SessionLocal
    from app.modules.auth import invitations
    from app.modules.auth.service import create_user
    from app.modules.matching.service import Expert

    cache: dict[int, Api] = {}

    def get(expert_id: int) -> Api:
        if expert_id not in cache:
            with SessionLocal() as db:
                expert = db.get(Expert, expert_id)
                if invitations.user_for_expert(db, expert_id) is None:
                    create_user(db, expert.email, expert.nom, PASSWORD, "investigateur", expert_id)
                email = expert.email
            r = raw.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
            assert r.status_code == 200, r.text
            cache[expert_id] = Api(raw, r.json()["access_token"])
        return cache[expert_id]
    return get


@pytest.fixture(scope="session")
def chosen_case(client, expert_api):
    """chosen_case(sign=True, description=None) -> (case_id, expert_api of the chosen expert)."""
    def make(sign: bool = True, description: str | None = None):
        body = {**MANDAT_FRAUDE, **({"description": description} if description else {})}
        cid = client.post("/api/v1/cases", json=body).json()["case_id"]
        eid = client.get(f"/api/v1/cases/{cid}/experts").json()["experts"][0]["id"]
        sid = client.post("/api/v1/solicitations", json={"case_id": cid, "expert_ids": [eid]}
                          ).json()["solicitations"][0]["id"]
        expert = expert_api(eid)
        assert expert.put(f"/api/v1/solicitations/{sid}/respond", json={"status": "accepted"}).status_code == 200
        assert client.post("/api/v1/solicitations/select", json={"case_id": cid, "expert_id": eid}).status_code == 200
        if sign:
            client.post(f"/api/v1/cases/{cid}/sign", json={"signatory_name": "Dupont"})
        return cid, expert
    return make
