import json
import time
from pathlib import Path

import pytest

from app.modules.audit.service import sha256_file
from app.modules.pv.nlp import analyze_text, fold, person_key
from app.modules.pv.rules import detect
from tests.conftest import MANDAT_FRAUDE

DATASET = json.loads((Path(__file__).parent / "data" / "pv_dataset.json").read_text(encoding="utf-8"))
CATEGORIES = {
    "personnes": (person_key, "personnes"),
    "lieux": (fold, "lieux"),
    "dates": (str, "dates_iso"),
    "montants": (float, "montants_valeurs"),
    "heures": (str, "heures"),
}


def _analyze_all():
    results, facts = {}, {}
    for pv in DATASET["pvs"]:
        r = analyze_text(pv["text"], pv["pv_id"], pv["witness"], 2025)
        results[pv["pv_id"]] = r
        facts.setdefault(pv["case"], []).extend(r["facts"])
    return results, facts


def test_ner_precision_and_recall_meet_spec():
    """Spec 7.6.8: precision >= 80%, recall >= 75% on the annotated PV set."""
    results, _ = _analyze_all()
    tp = fp = fn = 0
    for pv in DATASET["pvs"]:
        got_entities = results[pv["pv_id"]]["entities"]
        for expected_key, (norm, got_key) in CATEGORIES.items():
            expected = {norm(x) for x in pv[expected_key]}
            got = {norm(x) for x in got_entities[got_key]}
            tp += len(expected & got)
            fp += len(got - expected)
            fn += len(expected - got)
    precision, recall = tp / (tp + fp), tp / (tp + fn)
    print(f"NER precision={precision:.3f} recall={recall:.3f} (tp={tp} fp={fp} fn={fn})")
    assert precision >= 0.8
    assert recall >= 0.75


def test_inconsistency_types_match_expected_per_case():
    _, facts = _analyze_all()
    for case, expected in DATASET["expect_types"].items():
        found = sorted({i["type"] for i in detect(facts[case])})
        assert found == sorted(expected), f"{case}: got {found}, expected {sorted(expected)}"


def test_false_positive_rate_below_30_percent():
    _, facts = _analyze_all()
    expected_total = sum(len(v) for v in DATASET["expect_types"].values())
    found_total = sum(len(detect(f)) for f in facts.values())
    assert found_total > 0 and (found_total - expected_total) / found_total < 0.3


def test_temporal_inconsistency_names_both_dates_and_pvs():
    _, facts = _analyze_all()
    inc = detect(facts["fraude"])[0]
    assert inc["type"] == "temporelle" and inc["severity"] == "haute"
    assert "10/10/2025" in inc["description"] and "05/10/2025" in inc["description"]
    assert sorted(inc["pv_references"]) == ["fr-1", "fr-2"]
    assert len(inc["evidence"]) == 2


def test_absence_range_versus_sighting():
    a = analyze_text("M. Bernard est en vacances du 5 au 15 octobre 2025.", "a", "Julie Moreau", 2025)
    b = analyze_text("J'ai vu M. Bernard le 10/10/2025 au bureau de Lyon.", "b", "Paul Martin", 2025)
    incs = detect(a["facts"] + b["facts"])
    assert [i["type"] for i in incs] == ["temporelle"]
    assert "10/10/2025" in incs[0]["description"]


def test_sighting_outside_absence_range_is_not_flagged():
    a = analyze_text("M. Bernard est en vacances du 5 au 15 octobre 2025.", "a", "Julie Moreau", 2025)
    b = analyze_text("J'ai vu M. Bernard le 20/10/2025 au bureau de Lyon.", "b", "Paul Martin", 2025)
    assert detect(a["facts"] + b["facts"]) == []


def test_plane_makes_the_same_trip_plausible():
    plane = analyze_text("Je suis allé de Paris à Marseille en 1h30 en avion.", "p", "Thomas Roux", 2025)
    assert detect(plane["facts"]) == []
    road = analyze_text("Je suis allé de Paris à Marseille en 1h30 en voiture.", "p", "Thomas Roux", 2025)
    assert [i["type"] for i in detect(road["facts"])] == ["geographique"]


def test_date_parsing_variants():
    text = "Le 1er mars 2025, le 5/10/25, le 2025-11-02 et le 12.01.2025 à 192.168.1.50 avec 2.5 GB."
    got = analyze_text(text, "x", "Test Test", 2025)["entities"]["dates_iso"]
    assert got == ["2025-01-12", "2025-03-01", "2025-10-05", "2025-11-02"]


def test_amount_variants():
    text = "Virement de 1 200,50 euros, puis 75 000 € et 300 EUR."
    assert analyze_text(text, "x", "Test Test", 2025)["entities"]["montants_valeurs"] == [300.0, 1200.5, 75000.0]


def test_5000_word_pv_under_3_seconds():
    base = DATASET["pvs"][0]["text"]
    text = (base + "\n") * (5000 // len(base.split()) + 1)
    assert len(text.split()) >= 5000
    analyze_text("Warm up. M. Dupont est a Paris.", "w", "Test Test", 2025)
    start = time.perf_counter()
    analyze_text(text, "big", "Pierre Lambert", 2025)
    assert time.perf_counter() - start < 3


# ---------------------------------------------------------------- API

@pytest.fixture(scope="module")
def case_id(client):
    return client.post("/api/v1/cases", json=MANDAT_FRAUDE).json()["case_id"]


def _post(client, case_id, pv, **extra):
    return client.post("/api/v1/pv/analyze", json={
        "case_id": case_id, "pv_id": pv["pv_id"], "pv_text": pv["text"], "witness_name": pv["witness"], **extra})


def test_api_analyze_two_pvs_flags_inconsistency_and_hashes_file(client, case_id):
    first, second = DATASET["pvs"][0], DATASET["pvs"][1]
    r1 = _post(client, case_id, first)
    assert r1.status_code == 200
    assert r1.json()["incoherences"] == [] and r1.json()["score_coherence"] == 1.0
    r2 = _post(client, case_id, second)
    body = r2.json()
    assert [i["type"] for i in body["incoherences"]] == ["temporelle"]
    assert body["score_coherence"] == 0.8
    assert "Hugo Perrin" in body["entities"]["personnes"]

    stored = Path(client.get(f"/api/v1/pv?case_id={case_id}").json()["pvs"][0]["sha256"])  # hash exposed
    assert len(str(stored)) == 64
    logs = client.get(f"/api/v1/audit/logs?case_id={case_id}").json()["logs"]
    entry = [log for log in logs if log["module"] == "F"][0]
    assert entry["hash"] == r1.json()["sha256"]
    assert sha256_file(entry["file_path"]) == entry["hash"]
    assert client.get("/api/v1/audit/chain/verify").json()["valid"] is True


def test_api_reanalysis_is_idempotent(client, case_id):
    before = len(client.get(f"/api/v1/pv?case_id={case_id}").json()["pvs"])
    assert _post(client, case_id, DATASET["pvs"][0]).status_code == 200
    assert len(client.get(f"/api/v1/pv?case_id={case_id}").json()["pvs"]) == before


def test_api_report_and_pseudonymization(client, case_id):
    report = client.get(f"/api/v1/pv/report?case_id={case_id}").json()
    assert len(report["incoherences"]) == 1 and report["score_coherence"] == 0.8
    masked = client.get(f"/api/v1/pv/report?case_id={case_id}&pseudonymize=true").json()
    text = json.dumps(masked, ensure_ascii=False)
    for name in ("Lambert", "Girard", "Perrin", "Morel"):
        assert name not in text
    assert "Personne A" in text
    masked_one = _post(client, case_id, DATASET["pvs"][1], pseudonymize=True).json()
    assert "Perrin" not in json.dumps(masked_one, ensure_ascii=False)


def test_api_validation_and_errors(client, case_id):
    pv = DATASET["pvs"][0]
    assert client.post("/api/v1/pv/analyze", json={
        "case_id": "nope", "pv_id": "x1", "pv_text": pv["text"], "witness_name": "Test Test"}).status_code == 404
    assert _post(client, case_id, {**pv, "pv_id": "../evil"}).status_code == 422
    assert _post(client, case_id, {**pv, "text": "trop court"}).status_code == 422
