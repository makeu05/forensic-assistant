import os
import shutil
from pathlib import Path

import pytest

from app.modules.methodology.router import FORENSIC_TOOLS, build_methodology
from app.modules.reports.tech import optimize_chain, score_report
from tests.test_pv import DATASET

API = "/api/v1"
needs_latex = pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex not installed")


def _post_pv(expert, cid, index):
    pv = DATASET["pvs"][index]
    r = expert.post(f"{API}/pv/analyze", json={"case_id": cid, "pv_id": pv["pv_id"], "pv_text": pv["text"],
                                               "witness_name": pv["witness"]})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def fraud_mission(chosen_case):
    """A chosen case with the two contradicting fraud PVs already analysed."""
    cid, expert = chosen_case()
    _post_pv(expert, cid, 0)
    _post_pv(expert, cid, 1)
    return cid, expert


# ------------------------------------------------------------------ G: methodology

def test_knowledge_base_covers_at_least_ten_tools():
    assert sum(len(t["outils"]) for t in FORENSIC_TOOLS.values()) >= 10


def test_methodology_orders_actions_by_how_many_hypotheses_need_them(fraud_mission):
    cid, expert = fraud_mission
    m = expert.get(f"{API}/methodology?case_id={cid}").json()
    ids = [h["id"] for h in m["hypotheses"]]
    assert ids == ["fraude_operations", "manipulation_chronologie"]  # case type, then the temporal inconsistency
    plan = m["plan"]
    assert [p["priority"] for p in plan] == [1, 2]
    assert plan[0]["action"] == "analyse_logs" and set(plan[0]["justified_by"]) == set(ids)  # needed by both
    assert plan[1]["action"] == "analyse_disque"
    assert all(len(p["outils"]) >= 2 for p in plan)  # spec: at least 2 tools per hypothesis
    assert m["duree_totale_min"] == 7 and m["duree_totale_max"] == 13  # 3-5 h + 4-8 h, computed not hard-coded
    assert "2 hypothèse(s) sur 2" in plan[0]["why"]


def test_methodology_without_incoherences_only_uses_the_case_type():
    m = build_methodology("malware", [])
    assert [h["id"] for h in m["hypotheses"]] == ["infection_malware"]
    assert [p["action"] for p in m["plan"]] == ["malware_analysis", "analyse_logs", "analyse_disque"]


def test_methodology_is_for_the_investigator_of_the_case_only(client, expert_api, fraud_mission):
    cid, _ = fraud_mission
    assert client.get(f"{API}/methodology?case_id={cid}").status_code == 403
    assert expert_api(46).get(f"{API}/methodology?case_id={cid}").status_code == 404


# ------------------------------------------------------------ H: technical reports

def test_score_matches_the_specification_example():
    r = {"action": "analyse_logs", "outils": ["Splunk"], "resultats": "Connexion suspecte 192.168.1.50 a 03:42",
         "preuves": ["log_extract.txt", "screenshot.png"]}
    s = score_report(r)
    assert s["score"] == 0.6 and s["breakdown"] == {"completude": 0.4, "pertinence": 0.0, "preuves": 0.2}


def test_an_empty_field_does_not_count_as_present():
    s = score_report({"action": "x", "outils": [], "resultats": "  ", "preuves": []})
    assert s["details"]["champs_manquants"] == ["outils", "resultats", "preuves"]
    assert s["score"] == 0.1


def test_relevance_counts_french_and_english_concepts():
    text = "Empreinte SHA-256 relevée, horodatage cohérent, journaux corrélés, artefact extrait, signature valide"
    s = score_report({"action": "a", "outils": ["x"], "resultats": text, "preuves": ["1", "2", "3"]})
    assert s["score"] == 1.0 and s["details"]["concepts_absents"] == []


def test_chain_keeps_only_reports_from_half_a_point_best_first():
    scored = [{"rapport_id": "b", "action": "x", "score": 0.5, "preuves": ["p1", "p2", "p3"]},
              {"rapport_id": "a", "action": "y", "score": 0.85, "preuves": []},
              {"rapport_id": "c", "action": "z", "score": 0.49, "preuves": []}]
    chain = optimize_chain(scored)
    assert [c["rapport_id"] for c in chain] == ["a", "b"] and chain[1]["preuves_cles"] == ["p1", "p2"]


def test_reports_endpoint_ranks_stores_and_recommends(client, fraud_mission):
    cid, expert = fraud_mission
    strong = {"rapport_id": "r1", "action": "analyse_logs", "outils": ["Splunk"],
              "resultats": "Journaux corrélés, horodatage et empreinte hash vérifiés, artefact extrait",
              "preuves": ["log_extract.txt", "export.csv", "capture.png"]}
    weak = {"rapport_id": "r2", "action": "analyse_reseau", "outils": [], "resultats": "RAS", "preuves": []}
    r = expert.post(f"{API}/reports/analyze", json={"case_id": cid, "rapports": [strong, weak]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [x["rapport_id"] for x in body["rapports"]] == ["r1", "r2"] and body["rapports"][0]["rank"] == 1
    assert [c["rapport_id"] for c in body["chaine_optimale"]] == ["r1"]
    assert body["score_global"] == round((body["rapports"][0]["score"] + body["rapports"][1]["score"]) / 2, 2)
    text = " ".join(body["recommandations"])
    assert "r2" in text and "exclu de la chaîne" in text
    assert "Analyse de disque" in text  # planned by the methodology, no report covers it yet

    again = expert.post(f"{API}/reports/analyze", json={"case_id": cid, "rapports": [strong]}).json()
    assert len(again["rapports"]) == 2  # r1 updated in place, r2 untouched
    assert expert.get(f"{API}/reports/analysis?case_id={cid}").json()["chaine_optimale"] == body["chaine_optimale"]
    assert client.get(f"{API}/reports/analysis?case_id={cid}").status_code == 403
    assert expert.request("DELETE", f"{API}/reports/r2?case_id={cid}").status_code == 204
    assert len(expert.get(f"{API}/reports/analysis?case_id={cid}").json()["rapports"]) == 1


def test_report_input_is_validated(fraud_mission):
    cid, expert = fraud_mission
    bad = {"rapport_id": "../x", "action": "a", "outils": [], "resultats": "", "preuves": []}
    assert expert.post(f"{API}/reports/analyze", json={"case_id": cid, "rapports": [bad]}).status_code == 422
    assert expert.post(f"{API}/reports/analyze", json={"case_id": cid, "rapports": []}).status_code == 422


# ------------------------------------------------------------------- I: final report

def test_report_needs_at_least_one_pv(chosen_case):
    cid, expert = chosen_case()
    assert expert.post(f"{API}/reports/generate", json={"case_id": cid}).status_code == 409


@needs_latex
def test_final_report_pdf_versions_and_access(client, expert_api, fraud_mission):
    cid, expert = fraud_mission
    r = expert.post(f"{API}/reports/generate", json={"case_id": cid, "conclusion": "Les faits sont cohérents & \\input{x}."})
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["version"] == 1 and len(first["sha256"]) == 64 and len(first["outline"]) >= 5
    assert {s["key"] for s in first["outline"]} >= {"resume", "contexte", "methodologie", "analyse", "conclusion"}
    pdf = expert.get(first["pdf_url"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # the mandataire reads the report but cannot produce one; an outsider sees nothing
    assert client.get(first["pdf_url"]).status_code == 200
    assert client.get(f"{API}/reports?case_id={cid}").json()["reports"][0]["report_id"] == first["report_id"]
    assert client.post(f"{API}/reports/generate", json={"case_id": cid}).status_code == 403
    assert expert_api(47).get(first["pdf_url"]).status_code == 404

    second = expert.post(f"{API}/reports/generate", json={"case_id": cid}).json()
    assert second["version"] == 2
    listed = expert.get(f"{API}/reports?case_id={cid}").json()["reports"]
    assert [x["version"] for x in listed] == [2, 1]


@needs_latex
def test_report_source_contains_findings_and_escapes_hostile_text(fraud_mission):
    cid, expert = fraud_mission
    expert.post(f"{API}/reports/generate", json={"case_id": cid, "conclusion": r"Voir \input{/etc/passwd} & 100%"})
    folder = Path(os.environ["OUTPUT_DIR"]) / "reports" / cid
    source = max(folder.glob("*/rapport.tex"), key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8")
    assert "10/10/2025" in source and "05/10/2025" in source  # the temporal inconsistency
    assert "Chronologie impossible" in source and "Cha\\^ine de custody" in source
    assert r"\textbackslash{}input\{/etc/passwd\}" in source and r"100\%" in source


@needs_latex
def test_pseudonymized_report_hides_names(fraud_mission):
    cid, expert = fraud_mission
    r = expert.post(f"{API}/reports/generate", json={"case_id": cid, "pseudonymize": True})
    assert r.status_code == 201 and r.json()["pseudonymized"] is True
    folder = Path(os.environ["OUTPUT_DIR"]) / "reports" / cid
    source = max(folder.glob("*/rapport.tex"), key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8")
    for name in ("Lambert", "Girard", "Perrin"):
        assert name not in source
    assert "Personne A" in source


# ------------------------------------------------- PV detail, lifecycle, audit filters

def test_pv_detail_returns_highlight_segments(fraud_mission):
    cid, expert = fraud_mission
    pv = DATASET["pvs"][0]
    d = expert.get(f"{API}/pv/{pv['pv_id']}?case_id={cid}").json()
    assert "".join(s["text"] for s in d["segments"]) == pv["text"]  # nothing lost, nothing added
    labelled = {(s["label"], s["text"]) for s in d["segments"] if s["label"]}
    assert ("date", "10/10/2025") in labelled and ("montant", "50 000 euros") in labelled
    assert ("personne", "Sophie Girard") in labelled and ("lieu", "Lyon") in labelled
    assert d["verified"] is True and len(d["sha256"]) == 64
    assert [i["type"] for i in d["incoherences"]] == ["temporelle"] and d["incoherences"][0]["why"]


def test_pv_detail_pseudonymized_and_tamper_check(fraud_mission):
    cid, expert = fraud_mission
    masked = expert.get(f"{API}/pv/fr-1?case_id={cid}&pseudonymize=true").json()
    text = "".join(s["text"] for s in masked["segments"])
    assert "Girard" not in text and "Personne" in text and "Lambert" not in masked["witness_name"]
    path = Path(os.environ["OUTPUT_DIR"]) / "pv" / cid / "fr-2.txt"
    original = path.read_text(encoding="utf-8")
    try:
        path.write_text(original + " modifié", encoding="utf-8")
        assert expert.get(f"{API}/pv/fr-2?case_id={cid}").status_code == 409
    finally:
        path.write_text(original, encoding="utf-8")
    assert expert.get(f"{API}/pv/fr-2?case_id={cid}").status_code == 200


def test_pv_detail_unknown_pv_is_404(fraud_mission):
    cid, expert = fraud_mission
    assert expert.get(f"{API}/pv/zz-9?case_id={cid}").status_code == 404


def test_case_lifecycle_follows_the_work(client, chosen_case):
    cid, expert = chosen_case()

    def stages():
        c = client.get(f"{API}/cases/{cid}").json()
        return {s["key"]: s["done"] for s in c["stages"]}, c

    done, case = stages()
    assert done == {"mandat": True, "experts": True, "contrat": False, "preparation": False,
                    "analyse": False, "rapport": False}
    assert [s["key"] for s in case["stages"] if s["current"]] == ["contrat"] and case["progress"] == 0.33
    expert.post(f"{API}/mission/prepare", json={"case_id": cid})
    _post_pv(expert, cid, 0)
    done, case = stages()
    assert done["preparation"] and done["analyse"] and not done["rapport"]
    assert case["last_activity"] >= case["created_at"]
    listed = {c["case_id"]: c for c in client.get(f"{API}/cases").json()["cases"]}
    assert listed[cid]["stages"][1]["done"] is True


def test_audit_filters_and_no_absolute_paths(client, fraud_mission):
    cid, _ = fraud_mission
    only_f = client.get(f"{API}/audit/logs?case_id={cid}&module=F").json()
    assert only_f["total"] >= 2 and {log["module"] for log in only_f["logs"]} == {"F"}
    assert "F" in only_f["modules"] and "A" in only_f["modules"]
    by_actor = client.get(f"{API}/audit/logs?case_id={cid}&actor=experts.example").json()
    assert by_actor["total"] >= 2 and all("@experts.example" in log["user"] for log in by_actor["logs"])
    newest_first = client.get(f"{API}/audit/logs?case_id={cid}&order=desc").json()["logs"]
    assert [log["id"] for log in newest_first] == sorted((log["id"] for log in newest_first), reverse=True)
    none = client.get(f"{API}/audit/logs?case_id={cid}&action=does-not-exist").json()
    assert none["total"] == 0
    with_files = [log for log in only_f["logs"] if log["file"]]
    assert with_files and all(not Path(log["file"]).is_absolute() for log in with_files)


@needs_latex
def test_mission_guide_uses_the_investigators_edits(chosen_case):
    cid, expert = chosen_case()
    edited = {"case_id": cid, "questions": ["Question modifiée par l'expert ?", "  "],
              "suggested_witnesses": ["M. Témoin Test"], "checklist": ["Étape ajoutée"]}
    r = expert.post(f"{API}/mission/prepare", json=edited)
    assert r.status_code == 200
    assert r.json()["questions"] == ["Question modifiée par l'expert ?"]  # blank entries dropped
    assert r.json()["suggested_witnesses"] == ["M. Témoin Test"]
    source = (Path(os.environ["OUTPUT_DIR"]) / "guides" / cid / "guide.tex").read_text(encoding="utf-8")
    assert "Question modifiée par l'expert" in source and "M. Témoin Test" in source
    assert expert.post(f"{API}/mission/prepare", json={"case_id": cid, "questions": ["x"] * 61}).status_code == 422


def test_lifecycle_exposes_solicitation_counts(client, expert_api):
    cid = client.post(f"{API}/cases", json=DATASET_CASE).json()["case_id"]
    sols = client.post(f"{API}/solicitations", json={"case_id": cid, "expert_ids": [48, 49]}).json()["solicitations"]
    expert_api(48).put(f"{API}/solicitations/{sols[0]['id']}/respond", json={"status": "accepted"})
    expert_api(49).put(f"{API}/solicitations/{sols[1]['id']}/respond", json={"status": "refused", "reason": "indisponible"})
    got = client.get(f"{API}/cases/{cid}").json()["solicitations"]
    assert got == {"total": 2, "pending": 0, "accepted": 1, "refused": 1}


DATASET_CASE = {"case_type": "malware", "description": "Ransomware sur le serveur de fichiers de la société.",
                "priority": "moyenne", "mandataire": {"nom": "Dupont", "fonction": "juge_instruction"}}
