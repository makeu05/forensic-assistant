import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["AUDIT_LOG_PATH"] = f"{_tmp}/audit.jsonl"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


MANDAT_FRAUDE = {
    "case_type": "fraude_bancaire",
    "description": "Virements suspects de 50000 euros vers un compte etranger, analyse des logs bancaires.",
    "priority": "haute",
    "mandataire": {"nom": "Dupont", "fonction": "juge_instruction"},
}
