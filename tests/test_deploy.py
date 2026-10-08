import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.core.security import client_ip
from app.db import Base
from app.modules.matching.importer import import_experts, parse_csv, remove_demo_experts
from app.modules.matching.service import Expert
from app.modules.workflow.router import Solicitation

ROOT = Path(__file__).resolve().parent.parent
HEADER = "nom,email,competences,bio,annees_experience,disponibilite\n"


@pytest.fixture
def db(tmp_path):
    """An empty database of its own, so these tests never touch the shared one."""
    engine = create_engine(f"sqlite:///{tmp_path}/own.db")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session


# --------------------------------------------------------------- expert CSV import

def test_valid_csv_is_parsed_and_normalised():
    text = HEADER + "Camille Laurent,Camille.Laurent@Cabinet.fr,Forensic Bancaire|analyse_logs,Fraude,12,oui\n"
    result = parse_csv(text)
    assert result.errors == []
    assert result.rows == [{"nom": "Camille Laurent", "email": "camille.laurent@cabinet.fr",
                            "competences": ["forensic_bancaire", "analyse_logs"], "bio": "Fraude",
                            "annees_experience": 12, "disponibilite": True}]


def test_excel_style_file_is_understood():
    text = "\ufeffnom;email;competences;annees_experience;disponibilite\nNabil Haddad;n.haddad@cabinet.fr;malware|reseau;8;non\n"
    result = parse_csv(text)
    assert result.errors == [] and result.rows[0]["disponibilite"] is False and result.rows[0]["annees_experience"] == 8


def test_every_problem_is_reported_with_its_line_number():
    text = (HEADER + "X,not-an-email,malware,,5,oui\n" + "Bon Nom,ok@cabinet.fr,,,5,oui\n" +
            "Autre Nom,autre@cabinet.fr,malware,,99,oui\n" + "Dernier,dernier@cabinet.fr,malware,,5,peut-etre\n" +
            "Valide,valide@cabinet.fr,malware,,5,oui\n")
    result = parse_csv(text)
    assert [r["email"] for r in result.rows] == ["valide@cabinet.fr"]
    joined = "\n".join(result.errors)
    for line, fragment in ((2, "nom must be"), (2, "invalid email"), (3, "competence"), (4, "annees_experience"), (5, "disponibilite")):
        assert any(e.startswith(f"line {line}:") and fragment in e for e in result.errors), joined


def test_missing_columns_and_duplicate_addresses():
    assert "Missing column(s): competences" in parse_csv("nom,email\nA B,a@b.fr\n").errors[0]
    dup = parse_csv(HEADER + "A B,a@cabinet.fr,malware,,1,oui\nC D,A@cabinet.fr,malware,,1,oui\n")
    assert len(dup.rows) == 1 and "appears twice" in dup.errors[0]


def test_import_is_a_dry_run_unless_applied_and_never_overwrites(db):
    text = HEADER + "Camille Laurent,camille@cabinet.fr,forensic_bancaire,,12,oui\n"
    dry = import_experts(db, parse_csv(text), apply=False)
    assert len(dry.rows) == 1 and db.scalars(select(Expert)).all() == []
    import_experts(db, parse_csv(text), apply=True)
    stored = db.scalars(select(Expert)).one()
    assert stored.email == "camille@cabinet.fr" and stored.competences == ["forensic_bancaire"] and stored.annees_experience == 12
    again = import_experts(db, parse_csv(text.replace("Camille Laurent", "Someone Else")), apply=True)
    assert again.rows == [] and again.skipped == ["camille@cabinet.fr"]
    assert db.scalars(select(Expert)).one().nom == "Camille Laurent"  # untouched


def test_demo_experts_are_removed_only_when_nothing_refers_to_them(db):
    demo_free = Expert(nom="Demo Libre", email="libre@experts.example", competences=["x"])
    demo_asked = Expert(nom="Demo Sollicite", email="sollicite@experts.example", competences=["x"])
    real = Expert(nom="Vrai Expert", email="vrai@cabinet.fr", competences=["x"])
    db.add_all([demo_free, demo_asked, real])
    db.commit()
    db.add(Solicitation(case_id="c1", expert_id=demo_asked.id))
    db.commit()
    assert [e.nom for e in remove_demo_experts(db, apply=False)] == ["Demo Libre"]
    assert len(db.scalars(select(Expert)).all()) == 3  # dry run
    remove_demo_experts(db, apply=True)
    assert sorted(e.nom for e in db.scalars(select(Expert))) == ["Demo Sollicite", "Vrai Expert"]


def test_the_template_file_is_valid():
    assert parse_csv((ROOT / "docs" / "experts-template.csv").read_text(encoding="utf-8")).errors == []


# ------------------------------------------------------ client address behind a proxy

def _request(peer: str, forwarded: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "client": (peer, 5000), "headers": headers, "method": "GET", "path": "/"})


def test_forwarded_header_is_ignored_from_untrusted_peers(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "172.18.0.0/16")
    assert client_ip(_request("203.0.113.9", "1.2.3.4")) == "203.0.113.9"  # anyone can forge the header
    monkeypatch.delenv("TRUSTED_PROXIES")
    assert client_ip(_request("172.18.0.2", "1.2.3.4")) == "172.18.0.2"  # nothing trusted by default


def test_forwarded_header_is_believed_from_a_trusted_proxy(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "172.18.0.0/16, 10.0.0.1")
    assert client_ip(_request("172.18.0.2", "198.51.100.7")) == "198.51.100.7"
    # a forged first entry cannot win: the address added by our own proxy is the one that counts
    assert client_ip(_request("172.18.0.2", "6.6.6.6, 198.51.100.7")) == "198.51.100.7"
    assert client_ip(_request("172.18.0.2", "198.51.100.7, 10.0.0.1")) == "198.51.100.7"
    assert client_ip(_request("172.18.0.2")) == "172.18.0.2"  # no header: the proxy itself


def test_a_typo_in_trusted_proxies_trusts_nothing(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "not-an-ip, 172.18.0.999")
    assert client_ip(_request("172.18.0.2", "1.2.3.4")) == "172.18.0.2"


# ------------------------------------------------------------------ production guards

def _run_app(tmp_path, **env) -> subprocess.CompletedProcess:
    code = ("from fastapi.testclient import TestClient\nfrom app.main import app\n"
            "with TestClient(app) as c:\n    print('DOCS', c.get('/docs').status_code, c.get('/openapi.json').status_code)\n"
            "    print('HEALTH', c.get('/api/v1/health').status_code)\n")
    base = {k: v for k, v in os.environ.items() if k not in ("JWT_SECRET", "LOCARD_ENV", "LOCARD_DOCS", "LOCARD_SEED_DEMO")}
    base.update({"LOCARD_NO_DOTENV": "1", "DATABASE_URL": f"sqlite:///{tmp_path}/prod.db", "OUTPUT_DIR": str(tmp_path / "out"),
                 "AUDIT_LOG_PATH": str(tmp_path / "audit.jsonl"), **env})
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=base, capture_output=True, text=True, timeout=180)


def test_production_refuses_to_start_without_a_jwt_secret(tmp_path):
    r = _run_app(tmp_path, LOCARD_ENV="production")
    assert r.returncode != 0 and "JWT_SECRET is required" in r.stderr


def test_production_hides_the_docs_and_skips_the_demo_experts(tmp_path):
    r = _run_app(tmp_path, LOCARD_ENV="production", JWT_SECRET="p" * 40, LOCARD_SEED_DEMO="0")
    assert r.returncode == 0, r.stderr[-800:]
    assert "DOCS 404 404" in r.stdout and "HEALTH 200" in r.stdout
    engine = create_engine(f"sqlite:///{tmp_path}/prod.db")
    with sessionmaker(bind=engine)() as s:
        assert s.scalars(select(Expert)).all() == []  # no fake experts on a live server


def test_development_keeps_docs_and_seeds_the_demo_experts(tmp_path):
    r = _run_app(tmp_path)
    assert r.returncode == 0 and "DOCS 200 200" in r.stdout
    with sessionmaker(bind=create_engine(f"sqlite:///{tmp_path}/prod.db"))() as s:
        assert len(s.scalars(select(Expert)).all()) == 60
