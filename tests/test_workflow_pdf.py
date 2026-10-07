import pytest

from app.core.latex import tex
from tests.conftest import MANDAT_FRAUDE


def _case_with_experts(client):
    cid = client.post("/api/v1/cases", json=MANDAT_FRAUDE).json()["case_id"]
    ids = [e["id"] for e in client.get(f"/api/v1/cases/{cid}/experts").json()["experts"]]
    sols = client.post("/api/v1/solicitations", json={"case_id": cid, "expert_ids": ids}).json()["solicitations"]
    return cid, ids, sols


def test_state_machine(client):
    cid, ids, sols = _case_with_experts(client)
    s_acc, s_ref, s_pen = sols
    assert client.put(f"/api/v1/solicitations/{s_acc['id']}/respond", json={"status": "accepted"}).status_code == 200
    assert client.put(f"/api/v1/solicitations/{s_ref['id']}/respond",
                      json={"status": "refused", "reason": "indisponible"}).status_code == 200
    # cannot respond twice
    assert client.put(f"/api/v1/solicitations/{s_acc['id']}/respond", json={"status": "refused"}).status_code == 409
    # cannot choose refused or pending experts
    for eid in (s_ref["expert_id"], s_pen["expert_id"]):
        assert client.post("/api/v1/solicitations/select", json={"case_id": cid, "expert_id": eid}).status_code == 409
    ok = client.post("/api/v1/solicitations/select", json={"case_id": cid, "expert_id": s_acc["expert_id"]})
    assert ok.status_code == 200
    assert client.get(f"/api/v1/cases/{cid}").json()["status"] == "en_cours"
    # a second selection is refused
    assert client.post("/api/v1/solicitations/select", json={"case_id": cid, "expert_id": s_acc["expert_id"]}).status_code == 409


def test_contract_requires_chosen_expert(client):
    cid = client.post("/api/v1/cases", json=MANDAT_FRAUDE).json()["case_id"]
    assert client.post("/api/v1/contracts/generate", json={"case_id": cid}).status_code == 409


def test_tex_escaping():
    assert tex(r"\input{/etc/passwd} & 50% $x_1") == r"\textbackslash{}input\{/etc/passwd\} \& 50\% \$x\_1"


def _chosen_case(client, description=None):
    body = {**MANDAT_FRAUDE, **({"description": description} if description else {})}
    cid = client.post("/api/v1/cases", json=body).json()["case_id"]
    eid = client.get(f"/api/v1/cases/{cid}/experts").json()["experts"][0]["id"]
    sid = client.post("/api/v1/solicitations", json={"case_id": cid, "expert_ids": [eid]}).json()["solicitations"][0]["id"]
    client.put(f"/api/v1/solicitations/{sid}/respond", json={"status": "accepted"})
    client.post("/api/v1/solicitations/select", json={"case_id": cid, "expert_id": eid})
    return cid


@pytest.mark.skipif(__import__("shutil").which("pdflatex") is None, reason="pdflatex not installed")
def test_contract_pdf_and_hash(client):
    # hostile description must not break compilation or execute anything
    cid = _chosen_case(client, r"Virement \input{/etc/passwd} & 50% $ # _ { } ~ ^ suspect")
    r = client.post("/api/v1/contracts/generate", json={"case_id": cid})
    assert r.status_code == 201, r.text
    data = r.json()
    assert len(data["hash_sha256"]) == 64
    pdf = client.get(data["pdf_url"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


@pytest.mark.skipif(__import__("shutil").which("pdflatex") is None, reason="pdflatex not installed")
def test_mission_prepare(client):
    cid = _chosen_case(client)
    r = client.post("/api/v1/mission/prepare", json={"case_id": cid})
    assert r.status_code == 200
    assert len(r.json()["questions"]) >= 5
    assert client.get(r.json()["guide_pdf_url"]).content.startswith(b"%PDF")
