import pytest

from app.core.latex import tex
from tests.conftest import MANDAT_FRAUDE


def _case_with_experts(client):  # noqa: D103
    cid = client.post("/api/v1/cases", json=MANDAT_FRAUDE).json()["case_id"]
    ids = [e["id"] for e in client.get(f"/api/v1/cases/{cid}/experts").json()["experts"]]
    sols = client.post("/api/v1/solicitations", json={"case_id": cid, "expert_ids": ids}).json()["solicitations"]
    return cid, ids, sols


def test_state_machine(client, expert_api):
    cid, ids, sols = _case_with_experts(client)
    s_acc, s_ref, s_pen = sols
    acc, ref = expert_api(s_acc["expert_id"]), expert_api(s_ref["expert_id"])
    assert acc.put(f"/api/v1/solicitations/{s_acc['id']}/respond", json={"status": "accepted"}).status_code == 200
    assert ref.put(f"/api/v1/solicitations/{s_ref['id']}/respond",
                   json={"status": "refused", "reason": "indisponible"}).status_code == 200
    # cannot respond twice
    assert acc.put(f"/api/v1/solicitations/{s_acc['id']}/respond", json={"status": "refused"}).status_code == 409
    # cannot choose refused or pending experts
    for eid in (s_ref["expert_id"], s_pen["expert_id"]):
        assert client.post("/api/v1/solicitations/select", json={"case_id": cid, "expert_id": eid}).status_code == 409
    ok = client.post("/api/v1/solicitations/select", json={"case_id": cid, "expert_id": s_acc["expert_id"]})
    assert ok.status_code == 200
    assert client.get(f"/api/v1/cases/{cid}").json()["status"] == "en_cours"
    # a second selection is refused
    assert client.post("/api/v1/solicitations/select", json={"case_id": cid, "expert_id": s_acc["expert_id"]}).status_code == 409


def test_contract_requires_signature(client, chosen_case):
    cid, _ = chosen_case(sign=False)
    assert client.post("/api/v1/contracts/generate", json={"case_id": cid}).status_code == 409
    assert client.get(f"/api/v1/cases/{cid}").json()["signed"] is False
    s = client.post(f"/api/v1/cases/{cid}/sign", json={"signatory_name": "Dupont"})
    assert s.status_code == 200 and client.get(f"/api/v1/cases/{cid}").json()["signed"] is True


def test_list_cases(client):
    client.post("/api/v1/cases", json=MANDAT_FRAUDE)
    r = client.get("/api/v1/cases?limit=5").json()
    assert r["total"] >= 1 and len(r["cases"]) <= 5 and "signed" in r["cases"][0]


def test_contract_requires_chosen_expert(client):
    cid = client.post("/api/v1/cases", json=MANDAT_FRAUDE).json()["case_id"]
    assert client.post("/api/v1/contracts/generate", json={"case_id": cid}).status_code == 409


def test_tex_escaping():
    assert tex(r"\input{/etc/passwd} & 50% $x_1") == r"\textbackslash{}input\{/etc/passwd\} \& 50\% \$x\_1"


@pytest.mark.skipif(__import__("shutil").which("pdflatex") is None, reason="pdflatex not installed")
def test_contract_pdf_and_hash(client, chosen_case):
    # hostile description must not break compilation or execute anything
    cid, _ = chosen_case(description=r"Virement \input{/etc/passwd} & 50% $ # _ { } ~ ^ suspect")
    r = client.post("/api/v1/contracts/generate", json={"case_id": cid})
    assert r.status_code == 201, r.text
    data = r.json()
    assert len(data["hash_sha256"]) == 64
    pdf = client.get(data["pdf_url"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"/api/v1/contracts?case_id={cid}").json()["contract_id"] == data["contract_id"]


@pytest.mark.skipif(__import__("shutil").which("pdflatex") is None, reason="pdflatex not installed")
def test_mission_prepare(client, chosen_case):
    cid, expert = chosen_case()
    r = expert.post("/api/v1/mission/prepare", json={"case_id": cid})
    assert r.status_code == 200
    assert len(r.json()["questions"]) >= 5
    assert expert.get(r.json()["guide_pdf_url"]).content.startswith(b"%PDF")
