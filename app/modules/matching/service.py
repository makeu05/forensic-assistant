"""Module B: expert matching (TF-IDF cosine similarity + multicriteria score)."""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base

W_TEXT, W_DISPO, W_EXP = 0.6, 0.2, 0.2


class Expert(Base):
    __tablename__ = "experts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True)
    # JSON list works on SQLite and PostgreSQL; spec uses TEXT[] on PostgreSQL only.
    competences: Mapped[list] = mapped_column(JSON, default=list)
    bio: Mapped[str] = mapped_column(Text, default="")
    annees_experience: Mapped[int] = mapped_column(Integer, default=0)
    disponibilite: Mapped[bool] = mapped_column(Boolean, default=True)


def _norm(text: str) -> str:
    # competence tags use underscores (forensic_bancaire); split them so they match prose
    return text.lower().replace("_", " ")


def match_experts(description: str, case_type: str, experts: list[Expert], top_n: int = 3) -> list[dict]:
    """Return the top_n experts with score and justification (score in [0, 1])."""
    if not experts:
        return []
    query = _norm(f"{case_type} {description}")
    corpus = [query] + [_norm(" ".join(e.competences) + " " + (e.bio or "")) for e in experts]
    matrix = TfidfVectorizer().fit_transform(corpus)
    sims = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

    scored = []
    for e, sim in zip(experts, sims):
        text_s = float(sim) * W_TEXT
        dispo_s = W_DISPO if e.disponibilite else 0.0
        exp_s = min(e.annees_experience / 20, 1) * W_EXP
        total = round(text_s + dispo_s + exp_s, 4)
        scored.append({
            "id": e.id,
            "nom": e.nom,
            "competences": e.competences,
            "bio": e.bio,
            "annees_experience": e.annees_experience,
            "disponibilite": e.disponibilite,
            "weights": {"text": W_TEXT, "dispo": W_DISPO, "exp": W_EXP},
            "score": total,
            "breakdown": {
                "text_score": round(text_s, 2),
                "dispo_score": round(dispo_s, 2),
                "exp_score": round(exp_s, 2),
            },
            "justification": (
                f"Similarite textuelle: {text_s:.2f}, disponibilite: {dispo_s:.2f}, "
                f"experience ({e.annees_experience} ans): {exp_s:.2f}"
            ),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]
