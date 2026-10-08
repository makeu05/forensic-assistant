import pytest

from tests.test_pv import DATASET

API = "/api/v1"
FRAUD = {"case_type": "fraude_bancaire", "priority": "haute", "mandataire": {"nom": "Dupont", "fonction": "juge"},
         "description": "Virements suspects vers un compte étranger, analyse des journaux bancaires."}


@pytest.fixture(scope="module")
def mission(chosen_case):
    cid, expert = chosen_case()
    for i in (0, 1):
        pv = DATASET["pvs"][i]
        expert.post(f"{API}/pv/analyze", json={"case_id": cid, "pv_id": pv["pv_id"], "pv_text": pv["text"],
                                               "witness_name": pv["witness"]})
    expert.post(f"{API}/reports/analyze", json={"case_id": cid, "rapports": [
        {"rapport_id": "r1", "action": "analyse_logs", "outils": ["Splunk"], "resultats": "journaux et empreinte hash",
         "preuves": ["a.txt", "b.txt"]}]})
    return cid, expert


def test_expert_score_is_explained_with_its_breakdown(client):
    cid = client.post(f"{API}/cases", json=FRAUD).json()["case_id"]
    top = client.get(f"{API}/cases/{cid}/experts").json()["experts"][0]
    r = client.get(f"{API}/xai/explain", params={"module": "B", "case_id": cid, "entity_id": top["id"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["breakdown"] == {k: top["breakdown"][k] for k in ("text_score", "dispo_score", "exp_score")}
    assert body["details"]["rank"] == 1 and body["details"]["score"] == top["score"]
    assert top["nom"] in body["explanation"] and "Similarité textuelle" in body["explanation"]
    assert body["details"]["matched_keywords"], "the explanation names the words the expert shares with the mandate"
    missing = client.get(f"{API}/xai/explain", params={"module": "B", "case_id": cid, "entity_id": 999999})
    assert missing.status_code == 404


def test_expert_explanations_are_only_for_the_owner(other_mandataire, mission):
    cid, expert = mission
    assert other_mandataire.get(f"{API}/xai/explain", params={"module": "B", "case_id": cid, "entity_id": 1}).status_code == 404
    assert expert.get(f"{API}/xai/explain", params={"module": "B", "case_id": cid, "entity_id": 1}).status_code == 403


def test_inconsistency_is_explained(mission):
    cid, expert = mission
    r = expert.get(f"{API}/xai/explain", params={"module": "F", "case_id": cid, "entity_id": 0})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "10/10/2025" in body["explanation"] and "05/10/2025" in body["explanation"]
    assert body["details"]["rule"] == "action_apres_compromission" and len(body["details"]["evidence"]) == 2
    assert expert.get(f"{API}/xai/explain", params={"module": "F", "case_id": cid, "entity_id": 7}).status_code == 404
    assert expert.get(f"{API}/xai/explain", params={"module": "F", "case_id": cid, "entity_id": "abc"}).status_code == 404


def test_report_score_is_explained(mission):
    cid, expert = mission
    body = expert.get(f"{API}/xai/explain", params={"module": "H", "case_id": cid, "entity_id": "r1"}).json()
    assert body["breakdown"]["preuves"] == 0.2 and "2 jointe(s)" in body["explanation"]
    assert "chaîne optimale" in body["explanation"]
    assert expert.get(f"{API}/xai/explain", params={"module": "H", "case_id": cid, "entity_id": "nope"}).status_code == 404


def test_investigator_explanations_are_not_for_mandataires(client, mission):
    cid, _ = mission
    for module, entity in (("F", 0), ("H", "r1")):
        assert client.get(f"{API}/xai/explain", params={"module": module, "case_id": cid, "entity_id": entity}).status_code == 403


def test_unknown_module_and_anonymous(anon, mission):
    cid, expert = mission
    assert expert.get(f"{API}/xai/explain", params={"module": "Z", "case_id": cid, "entity_id": 1}).status_code == 422
    assert anon.get(f"{API}/xai/explain", params={"module": "B", "case_id": cid, "entity_id": 1}).status_code == 401
