"""Module F, second detector: contradictions between statements, suggested by a language model.

The rules in rules.py only recognise a few phrasings of a contradiction. A French natural language
inference (NLI) model reads two sentences and says how likely it is that they contradict each other.
Its answers are SUGGESTIONS TO VERIFY, kept apart from the rule-based findings and outside the
coherence score. Why that caution, and how the choices below were made, is in experiments/pv_nli/README.md.

What the experiment showed, in short:
- one small model is enough: a model 47 times slower gave no better ranking on whole statements;
- sentence pairs worth checking are found by shared words (no embedding model needed);
- only the best few suggestions per pair of statements, above a high minimum score, are worth showing.

The torch and transformers libraries are optional. Without them (or with LOCARD_ML=0) this module reports
itself unavailable and the rest of Locard works exactly as before.

Settings (environment):
  LOCARD_ML                  auto (default) or 0 to switch the feature off
  LOCARD_NLI_MODEL           Hugging Face model id, default cmarkea/distilcamembert-base-nli (MIT, 272 MB)
  LOCARD_NLI_MIN_SCORE       lowest contradiction probability shown, default 0.95
  LOCARD_NLI_CAP             suggestions kept per pair of statements, default 3
  LOCARD_NLI_MAX_CANDIDATES  sentence pairs scored per pair of statements, default 120
  HF_HOME, HF_HUB_OFFLINE    where models are cached; set HF_HUB_OFFLINE=1 once the model is downloaded
"""
import importlib.util
import os
import re
import threading
import time
from dataclasses import dataclass

from app.modules.pv.nlp import _sentences, fold

DEFAULT_MODEL = "cmarkea/distilcamembert-base-nli"
MIN_WORDS = 4               # shorter sentences carry no checkable claim
MAX_SENTENCES = 150         # per PV, to bound the work on a huge statement
EXCERPT = 240               # rule evidence is cut at this length (see pv/nlp.py), so duplicates are matched on it
FUNCTION_WORDS = set("""dans avec pour cette ainsi alors apres avant aucun aucune autre comme depuis donc elle elles entre encore
etait etaient etais etre avait avaient avoir fait faire leur leurs mais meme moins nous plus puis quand sans sont sous tout tous
toute toutes tres vers vous votre notre mon mes son ses nos aussi cela celui celle ceux ete suis ont qui que quoi dont lors jusqu
ensuite pendant seul seule seulement jamais toujours deja rien personne""".split())


def settings() -> dict:
    def number(name: str, default, cast):
        try:
            return cast(os.getenv(name, default))
        except ValueError:
            return cast(default)
    return {
        "model": os.getenv("LOCARD_NLI_MODEL", DEFAULT_MODEL),
        "min_score": min(0.999, max(0.0, number("LOCARD_NLI_MIN_SCORE", 0.95, float))),
        "cap": max(1, number("LOCARD_NLI_CAP", 3, int)),
        "max_candidates": max(1, number("LOCARD_NLI_MAX_CANDIDATES", 120, int)),
    }


def availability() -> tuple[bool, str]:
    """(usable, reason when not). Checks the libraries only: it never loads a model."""
    if os.getenv("LOCARD_ML", "auto").lower() in {"0", "off", "false", "no"}:
        return False, "Le modèle est désactivé (LOCARD_ML=0)."
    missing = [m for m in ("torch", "transformers") if importlib.util.find_spec(m) is None]
    if missing:
        return False, f"Les bibliothèques {', '.join(missing)} ne sont pas installées (voir requirements-ml.txt)."
    return True, ""


class NliModel:
    """A sequence-classification NLI model. Loaded once, on first use (several seconds), then kept in memory."""

    def __init__(self, name: str):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self._torch = torch
        self.name = name
        self.tokenizer = AutoTokenizer.from_pretrained(name)
        # safetensors only: a pickle-based checkpoint could run code when it is loaded
        self.model = AutoModelForSequenceClassification.from_pretrained(name, use_safetensors=True).eval()
        labels = {int(i): str(label).lower() for i, label in self.model.config.id2label.items()}
        self.contradiction = next(i for i, label in labels.items() if label.startswith("contra"))

    def p_contradiction(self, premises: list[str], hypotheses: list[str], batch: int = 16) -> list[float]:
        out: list[float] = []
        with self._torch.no_grad():
            for i in range(0, len(premises), batch):
                enc = self.tokenizer(premises[i:i + batch], hypotheses[i:i + batch], return_tensors="pt",
                                     padding=True, truncation=True, max_length=128)
                probs = self._torch.softmax(self.model(**enc).logits, dim=-1)
                out += probs[:, self.contradiction].tolist()
        return out


_models: dict[str, NliModel] = {}
_models_lock = threading.Lock()


def get_model(name: str | None = None) -> NliModel:
    name = name or settings()["model"]
    with _models_lock:
        if name not in _models:
            _models[name] = NliModel(name)
        return _models[name]


@dataclass(frozen=True)
class Sentence:
    pv_id: str
    index: int
    text: str
    tokens: frozenset


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def prefix_tokens(text: str, n: int = 5) -> frozenset:
    """Light stand-in for lemmas: accent-free lowercase words of 5+ letters (or numbers), cut to their first n letters.
    "connexion" and "connexions" meet, "bloqué" and "bloquer" meet, and it needs no language model."""
    words = re.findall(r"[a-z0-9]+", fold(text))
    return frozenset(w[:n] for w in words if (len(w) >= 5 or w.isdigit()) and w not in FUNCTION_WORDS)


HEADER = re.compile(r"^(date|cas|temoin|suspect|investigateur|signature)\b[^.]{0,40}:")


def is_header(sentence: str) -> bool:
    """Form lines of a PV ("Date : 12/10/2025", "Témoin : …") and all-capitals titles carry no claim to check."""
    return sentence.isupper() or bool(HEADER.match(fold(sentence)))


def split_sentences(pv_id: str, text: str) -> list[Sentence]:
    """The checkable sentences of a PV: not form headers, not questions, at least a few words long."""
    out: list[Sentence] = []
    for start, end in _sentences(text):
        sentence = norm(text[start:end])
        if len(sentence.split()) < MIN_WORDS or sentence.endswith("?") or is_header(sentence):
            continue
        out.append(Sentence(pv_id, len(out), sentence, prefix_tokens(sentence)))
        if len(out) >= MAX_SENTENCES:
            break
    return out


def candidate_pairs(a: list[Sentence], b: list[Sentence], limit: int) -> list[tuple[Sentence, Sentence, list[str]]]:
    """Sentence pairs that share at least one word stem, those sharing the most first, at most `limit`."""
    pairs = []
    for sa in a:
        for sb in b:
            shared = sa.tokens & sb.tokens
            if shared:
                pairs.append((len(shared), sa, sb, sorted(shared)))
    pairs.sort(key=lambda p: (-p[0], p[1].index, p[2].index))
    return [(sa, sb, shared) for _, sa, sb, shared in pairs[:limit]]


def find_suggestions(pvs: dict[str, str], model, *, min_score: float, cap: int, max_candidates: int,
                     skip: set[frozenset] | None = None) -> tuple[list[dict], dict]:
    """Suggest contradictions between the statements of one case.

    `pvs` maps a PV id to its text. Every pair of different PVs is compared (never a PV with itself). `skip` holds
    sentence pairs the rules already reported, as frozensets of their first EXCERPT characters, so nothing is shown twice.
    Returns the suggestions (best first) and statistics about the work done.
    """
    skip = skip or set()
    started = time.perf_counter()
    split = {pv_id: split_sentences(pv_id, text) for pv_id, text in pvs.items()}
    ids = list(pvs)
    suggestions: list[dict] = []
    stats = {"pv_pairs": 0, "candidates": 0, "pairs_scored": 0, "already_found_by_rules": 0}
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            stats["pv_pairs"] += 1
            cands = candidate_pairs(split[ids[x]], split[ids[y]], max_candidates)
            stats["candidates"] += len(cands)
            if not cands:
                continue
            forward = model.p_contradiction([c[0].text for c in cands], [c[1].text for c in cands])
            backward = model.p_contradiction([c[1].text for c in cands], [c[0].text for c in cands])
            stats["pairs_scored"] += 2 * len(cands)
            scored = []
            for (sa, sb, shared), f, r in zip(cands, forward, backward):
                score = max(f, r)
                if score < min_score:
                    continue
                if frozenset((sa.text[:EXCERPT], sb.text[:EXCERPT])) in skip:
                    stats["already_found_by_rules"] += 1
                    continue
                scored.append({"pv_a": sa.pv_id, "pv_b": sb.pv_id, "sentence_a": sa.text, "sentence_b": sb.text,
                               "score": round(score, 4), "p_ab": round(f, 4), "p_ba": round(r, 4), "shared": shared})
            suggestions += sorted(scored, key=lambda s: -s["score"])[:cap]
    stats["seconds"] = round(time.perf_counter() - started, 2)
    return sorted(suggestions, key=lambda s: -s["score"]), stats
