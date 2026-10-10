import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.modules.audit.service import AuditLog
from app.modules.pv import semantic
from app.modules.pv.semantic import candidate_pairs, find_suggestions, prefix_tokens, split_sentences
from app.modules.pv.semantic_api import SemanticRun
from tests.test_pv import DATASET

API = "/api/v1"


class Stub:
    """A stand-in for the NLI model: scores come from a function, so tests need no download."""

    def __init__(self, rule):
        self.rule, self.calls = rule, 0

    def p_contradiction(self, premises, hypotheses):
        self.calls += len(premises)
        return [self.rule(a, b) for a, b in zip(premises, hypotheses)]


def negation_rule(a: str, b: str) -> float:
    """High when exactly one of the two sentences says 'ne contenait', low otherwise."""
    return 0.99 if ("ne contenait" in a) != ("ne contenait" in b) else 0.2


@pytest.fixture
def stub(monkeypatch):
    model = Stub(negation_rule)
    monkeypatch.setattr(semantic, "availability", lambda: (True, ""))
    monkeypatch.setattr(semantic, "get_model", lambda name=None: model)
    return model


PV_A = ("Le fichier contenait plus de dix mille lignes. Le technicien est arrivé à huit heures le matin. "
        "Je travaille dans ce service depuis longtemps.")
PV_B = ("Le fichier ne contenait qu'une cinquantaine de lignes. Le technicien est parti à midi après l'intervention. "
        "Mon bureau est au troisième étage du bâtiment.")


def _add_pv(expert, cid, pv_id, witness, text):
    r = expert.post(f"{API}/pv/analyze", json={"case_id": cid, "pv_id": pv_id, "pv_text": text, "witness_name": witness})
    assert r.status_code == 200, r.text


@pytest.fixture
def case_with_two_pvs(chosen_case):
    cid, expert = chosen_case()
    _add_pv(expert, cid, "sa", "Témoin Alpha", PV_A)
    _add_pv(expert, cid, "sb", "Témoin Bravo", PV_B)
    return cid, expert


# ------------------------------------------------------------------ the pure logic

def test_inflections_share_stems_and_function_words_do_not():
    assert prefix_tokens("Trois connexions suspectes") & prefix_tokens("Une seule connexion suspecte")
    assert prefix_tokens("Le compte est bloqué") & prefix_tokens("Elle a bloqué le compte")
    assert not prefix_tokens("Il était dans la salle") & prefix_tokens("Elle était sans aucune idée")  # only function words
    assert "50" in prefix_tokens("Il a viré 50 euros")  # numbers count


def test_split_drops_headers_questions_and_fragments():
    text = ("PROCES-VERBAL D'AUDITION\nDate : 12/10/2025\nTémoin : Pierre Lambert\n\nDECLARATION :\n"
            "Je suis comptable depuis neuf ans. Suspect prétend avoir quitté Paris à huit heures. "
            "Pourquoi avez-vous fait cela ? Oui.\n")
    assert [s.text for s in split_sentences("x", text)] == [
        "Je suis comptable depuis neuf ans.", "Suspect prétend avoir quitté Paris à huit heures."]


def test_candidates_need_a_shared_word_and_are_capped():
    a = split_sentences("a", "La porte était fermée à clé. Le virement partait vendredi matin. Mon chat dort dehors toute la journée.")
    b = split_sentences("b", "La porte restait ouverte la nuit. Une banque a appelé vendredi après-midi. Rien d'autre à signaler ici.")
    pairs = [(x.text.split()[1], y.text.split()[1]) for x, y, _ in candidate_pairs(a, b, limit=10)]
    assert ("porte", "porte") in pairs and ("virement", "banque") in pairs
    assert len(pairs) == 2  # nothing else shares a word
    assert len(candidate_pairs(a, b, limit=1)) == 1


def test_floor_cap_and_order():
    scores = {"s1": 0.99, "s2": 0.97, "s3": 0.96, "s4": 0.60}

    def rule(a, b):  # only the sentences of PV A carry a marker, so the score does not depend on the direction
        return next((v for k, v in scores.items() if k in a + b), 0.0)

    pvs = {"A": "Le serveur s1 fonctionnait normalement. Le serveur s2 fonctionnait normalement. "
                "Le serveur s3 fonctionnait normalement. Le serveur s4 fonctionnait normalement.",
           "B": "Un serveur fonctionnait normalement."}
    found, stats = find_suggestions(pvs, Stub(rule), min_score=0.95, cap=2, max_candidates=100)
    assert [s["score"] for s in found] == [0.99, 0.97]  # cap of 2, best first, s4 under the floor
    assert stats["pv_pairs"] == 1 and stats["pairs_scored"] == 2 * stats["candidates"]


def test_a_pv_is_never_compared_with_itself():
    model = Stub(lambda a, b: 0.99)
    found, stats = find_suggestions({"A": "Le serveur était éteint ce matin. Le serveur était allumé ce matin."},
                                    model, min_score=0.5, cap=5, max_candidates=50)
    assert found == [] and model.calls == 0 and stats["pv_pairs"] == 0


def test_pairs_already_reported_by_the_rules_are_skipped():
    a, b = "La porte était fermée à clé ce matin.", "La porte était ouverte ce matin."
    key = frozenset((a, b))
    found, stats = find_suggestions({"A": a, "B": b}, Stub(lambda x, y: 0.99), min_score=0.5, cap=3, max_candidates=10,
                                    skip={key})
    assert found == [] and stats["already_found_by_rules"] == 1


def test_settings_defaults_and_unreadable_values(monkeypatch):
    for name in ("LOCARD_NLI_MODEL", "LOCARD_NLI_MIN_SCORE", "LOCARD_NLI_CAP", "LOCARD_NLI_MAX_CANDIDATES"):
        monkeypatch.delenv(name, raising=False)
    cfg = semantic.settings()
    assert cfg == {"model": "cmarkea/distilcamembert-base-nli", "min_score": 0.95, "cap": 3, "max_candidates": 120}
    monkeypatch.setenv("LOCARD_NLI_MIN_SCORE", "not-a-number")
    monkeypatch.setenv("LOCARD_NLI_CAP", "0")
    assert semantic.settings()["min_score"] == 0.95 and semantic.settings()["cap"] == 1  # a typo never breaks the feature


def test_the_feature_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("LOCARD_ML", "0")
    ok, reason = semantic.availability()
    assert ok is False and "LOCARD_ML=0" in reason


def test_missing_libraries_are_reported_not_crashed(monkeypatch):
    monkeypatch.delenv("LOCARD_ML", raising=False)
    monkeypatch.setattr(semantic.importlib.util, "find_spec", lambda name: None)
    ok, reason = semantic.availability()
    assert ok is False and "torch" in reason and "requirements-ml.txt" in reason


# ----------------------------------------------------------------------- the API

def test_status(chosen_case, stub):
    _, expert = chosen_case()
    body = expert.get(f"{API}/semantic/status").json()
    assert body["available"] is True and body["min_score"] == 0.95 and body["cap"] == 3 and body["model"]


def test_run_stores_suggestions_apart_from_the_rule_findings(case_with_two_pvs, stub):
    cid, expert = case_with_two_pvs
    assert expert.get(f"{API}/semantic/suggestions", params={"case_id": cid}).json()["status"] == "none"
    r = expert.post(f"{API}/semantic/run", json={"case_id": cid})
    assert r.status_code == 202 and r.json() == {"status": "running"}

    body = expert.get(f"{API}/semantic/suggestions", params={"case_id": cid}).json()
    assert body["status"] == "done" and body["stale"] is False and body["error"] is None
    assert len(body["suggestions"]) == 1
    s = body["suggestions"][0]
    assert (s["pv_a"], s["pv_b"]) == ("sa", "sb") and "dix mille lignes" in s["sentence_a"] and "cinquantaine" in s["sentence_b"]
    assert s["score"] == 0.99 and "fichi" in s["shared"]
    assert "ne comptent pas dans le score" in body["disclaimer"] and body["stats"]["suggestions"] == 1
    # the rule-based side is untouched: no inconsistency, coherence stays at 100
    pv = expert.get(f"{API}/pv/sa", params={"case_id": cid}).json()
    assert pv["incoherences"] == [] and pv["score_coherence"] == 1.0


def test_results_go_stale_when_the_pvs_change_and_a_new_run_replaces_them(case_with_two_pvs, stub):
    cid, expert = case_with_two_pvs
    expert.post(f"{API}/semantic/run", json={"case_id": cid})
    _add_pv(expert, cid, "sc", "Témoin Charlie", "Le fichier contenait plus de dix mille lignes selon moi, sans aucun doute.")
    assert expert.get(f"{API}/semantic/suggestions", params={"case_id": cid}).json()["stale"] is True
    expert.post(f"{API}/semantic/run", json={"case_id": cid})
    fresh = expert.get(f"{API}/semantic/suggestions", params={"case_id": cid}).json()
    assert fresh["stale"] is False and {(s["pv_a"], s["pv_b"]) for s in fresh["suggestions"]} == {("sa", "sb"), ("sb", "sc")}


def test_the_rules_findings_are_not_repeated(chosen_case, stub, monkeypatch):
    cid, expert = chosen_case()
    for pv in DATASET["pvs"][6:8]:  # the open door / closed door statements the rules already catch
        _add_pv(expert, cid, pv["pv_id"], pv["witness"], pv["text"])
    monkeypatch.setattr(stub, "rule", lambda a, b: 0.99)
    expert.post(f"{API}/semantic/run", json={"case_id": cid})
    body = expert.get(f"{API}/semantic/suggestions", params={"case_id": cid}).json()
    assert body["stats"]["already_found_by_rules"] >= 1
    assert not any("fermée" in s["sentence_a"] + s["sentence_b"] and "ouverte" in s["sentence_a"] + s["sentence_b"]
                   for s in body["suggestions"])


def test_cannot_run_without_the_model_or_with_a_single_pv(chosen_case, case_with_two_pvs, monkeypatch):
    cid, expert = case_with_two_pvs
    monkeypatch.setattr(semantic, "availability", lambda: (False, "Le modèle est désactivé (LOCARD_ML=0)."))
    r = expert.post(f"{API}/semantic/run", json={"case_id": cid})
    assert r.status_code == 503 and "désactivé" in r.json()["detail"]
    assert expert.get(f"{API}/semantic/status").json()["available"] is False
    assert expert.get(f"{API}/semantic/suggestions", params={"case_id": cid}).json()["available"] is False

    monkeypatch.setattr(semantic, "availability", lambda: (True, ""))
    lonely_cid, lonely = chosen_case()
    _add_pv(lonely, lonely_cid, "only", "Seul Témoin", PV_A)
    r = lonely.post(f"{API}/semantic/run", json={"case_id": lonely_cid})
    assert r.status_code == 409 and "deux PV" in r.json()["detail"]


def test_a_run_in_progress_blocks_a_second_one_until_it_is_stale(case_with_two_pvs, stub):
    cid, expert = case_with_two_pvs
    expert.post(f"{API}/semantic/run", json={"case_id": cid})
    with SessionLocal() as db:
        run = db.get(SemanticRun, cid)
        run.status, run.started_at = "running", datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        db.commit()
    assert expert.post(f"{API}/semantic/run", json={"case_id": cid}).status_code == 409
    with SessionLocal() as db:  # a run "in progress" for an hour belongs to a dead server process
        run = db.get(SemanticRun, cid)
        run.started_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds").replace("+00:00", "Z")
        db.commit()
    shown = expert.get(f"{API}/semantic/suggestions", params={"case_id": cid}).json()
    assert shown["status"] == "failed" and "interrompue" in shown["error"]
    assert expert.post(f"{API}/semantic/run", json={"case_id": cid}).status_code == 202


def test_a_model_failure_is_stored_and_never_crashes_the_request(case_with_two_pvs, monkeypatch):
    cid, expert = case_with_two_pvs
    monkeypatch.setattr(semantic, "availability", lambda: (True, ""))

    def broken(name=None):
        raise OSError("model files not found")

    monkeypatch.setattr(semantic, "get_model", broken)
    assert expert.post(f"{API}/semantic/run", json={"case_id": cid}).status_code == 202
    body = expert.get(f"{API}/semantic/suggestions", params={"case_id": cid}).json()
    assert body["status"] == "failed" and "OSError" in body["error"] and body["suggestions"] == []
    with SessionLocal() as db:
        assert db.scalars(select(AuditLog).where(AuditLog.action == "semantic_run_failed", AuditLog.case_id == cid)).first()


def test_a_modified_pv_file_stops_the_run(case_with_two_pvs, stub):
    cid, expert = case_with_two_pvs
    path = Path(os.environ["OUTPUT_DIR"]) / "pv" / cid / "sa.txt"
    original = path.read_text(encoding="utf-8")
    try:
        path.write_text(original + " Ajout frauduleux.", encoding="utf-8")
        expert.post(f"{API}/semantic/run", json={"case_id": cid})
        body = expert.get(f"{API}/semantic/suggestions", params={"case_id": cid}).json()
        assert body["status"] == "failed" and "Integrity check failed" in body["error"]
    finally:
        path.write_text(original, encoding="utf-8")


def test_run_is_audited_without_statement_content(case_with_two_pvs, stub):
    cid, expert = case_with_two_pvs
    expert.post(f"{API}/semantic/run", json={"case_id": cid})
    with SessionLocal() as db:
        entry = db.scalars(select(AuditLog).where(AuditLog.action == "semantic_run", AuditLog.case_id == cid)).one()
        assert entry.user.endswith("@experts.example") and entry.payload["suggestions"] == 1
        assert "mille lignes" not in json.dumps(entry.payload)


def test_names_can_be_pseudonymised(chosen_case, stub, monkeypatch):
    cid, expert = chosen_case()
    _add_pv(expert, cid, "na", "Pierre Lambert", "M. Hugo Perrin a signé le document de transfert avec beaucoup de soin.")
    _add_pv(expert, cid, "nb", "Claire Morel", "Je confirme que M. Hugo Perrin n'a jamais signé aucun document de transfert.")
    monkeypatch.setattr(stub, "rule", lambda a, b: 0.99)
    expert.post(f"{API}/semantic/run", json={"case_id": cid})
    plain = expert.get(f"{API}/semantic/suggestions", params={"case_id": cid}).json()
    assert "Perrin" in json.dumps(plain, ensure_ascii=False)
    masked = expert.get(f"{API}/semantic/suggestions", params={"case_id": cid, "pseudonymize": True}).json()
    assert "Perrin" not in json.dumps(masked, ensure_ascii=False) and "Personne" in json.dumps(masked, ensure_ascii=False)


def test_only_the_cases_investigator_can_use_it(client, anon, expert_api, case_with_two_pvs, stub):
    cid, expert = case_with_two_pvs
    for call in (lambda c: c.get(f"{API}/semantic/status"), lambda c: c.post(f"{API}/semantic/run", json={"case_id": cid}),
                 lambda c: c.get(f"{API}/semantic/suggestions", params={"case_id": cid})):
        assert call(client).status_code == 403  # a mandataire
        assert call(anon).status_code == 401
    outsider = expert_api(44)
    assert outsider.post(f"{API}/semantic/run", json={"case_id": cid}).status_code == 404
    assert outsider.get(f"{API}/semantic/suggestions", params={"case_id": cid}).status_code == 404


# -------------------------------------------------- the real model (skipped when unavailable)

@pytest.fixture(scope="module")
def real_model():
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return semantic.get_model()
    except Exception as e:  # noqa: BLE001 - libraries or model files absent: the stub tests still cover the logic
        pytest.skip(f"real model not available here: {type(e).__name__}")


def test_real_model_flags_a_clear_contradiction_and_stays_quiet_on_a_paraphrase(real_model):
    contradiction = find_suggestions(
        {"A": "Le contrat prévoyait une clause de confidentialité.", "B": "Le contrat ne contenait aucune clause de confidentialité."},
        real_model, min_score=0.95, cap=3, max_candidates=10)[0]
    assert len(contradiction) == 1 and contradiction[0]["score"] >= 0.95
    paraphrase = find_suggestions(
        {"A": "Les pirates ont chiffré les fichiers du serveur.", "B": "Les fichiers du serveur ont été chiffrés par les attaquants."},
        real_model, min_score=0.95, cap=3, max_candidates=10)[0]
    assert paraphrase == []


def test_real_model_scores_are_probabilities_and_rank_opposites_above_unrelated(real_model):
    scores = real_model.p_contradiction(["La porte était fermée."] * 2, ["La porte était ouverte.", "Il pleuvait."])
    assert all(0.0 <= p <= 1.0 for p in scores) and scores[0] > scores[1]
