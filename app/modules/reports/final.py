"""Module I: the final expertise report (LaTeX to PDF) with SHA-256 integrity hash.

It compiles what the other modules produced: the mandate (A, C), the PV analysis (F), the
hypotheses and plan (G), the technical reports (H) and the chain of custody (J). Every
generation is a new numbered version; earlier versions are kept.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.files import Encoding, file_answer
from app.core.latex import LatexError, render_pdf
from app.db import Base, get_db
from app.modules.audit.service import AuditLog, log_action, sha256_file, verify_chain
from app.modules.auth.access import case_for
from app.modules.auth.router import current_user, require_role
from app.modules.auth.service import User
from app.modules.cases.router import MandateSignature
from app.modules.contracts.router import Contract, output_dir
from app.modules.matching.service import Expert
from app.modules.methodology.router import build_methodology
from app.modules.pv.router import Pv, _all_facts, _case_pvs, _mask, _pseudonymizer
from app.modules.pv.rules import detect
from app.modules.reports.tech import analysis_for_case

router = APIRouter(prefix="/reports", tags=["I - Final report"])

CASE_LABEL = {"fraude_bancaire": "Fraude bancaire", "intrusion_reseau": "Intrusion réseau", "malware": "Logiciel malveillant"}
TYPE_LABEL = {"temporelle": "Incohérence temporelle", "geographique": "Incohérence géographique",
              "factuelle": "Incohérence factuelle"}
MAX_AUDIT_ROWS = 150


class FinalReport(Base):
    __tablename__ = "final_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer)
    pdf_path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    generated_at: Mapped[str] = mapped_column(String(40))
    generated_by: Mapped[str] = mapped_column(String(254))
    pseudonymized: Mapped[bool] = mapped_column(Boolean, default=False)
    outline: Mapped[str] = mapped_column(Text)  # JSON: sections for the on-screen preview


class GenerateIn(BaseModel):
    case_id: str
    conclusion: str = Field(default="", max_length=6000)
    pseudonymize: bool = False


def _ser(r: FinalReport) -> dict:
    return {"report_id": r.id, "case_id": r.case_id, "version": r.version, "sha256": r.sha256,
            "generated_at": r.generated_at, "generated_by": r.generated_by, "pseudonymized": r.pseudonymized,
            "pdf_url": f"/api/v1/reports/{r.id}/download", "outline": json.loads(r.outline)}


def _outline(ctx: dict) -> list[dict]:
    return [
        {"key": "resume", "title": "Résumé exécutif", "points": [
            f"{len(ctx['pvs'])} procès-verbal(aux) analysé(s)",
            f"{len(ctx['incoherences'])} incohérence(s) dont {ctx['high_count']} de sévérité haute",
            f"Score de cohérence : {ctx['coherence_pct']} %"]},
        {"key": "contexte", "title": "Contexte et mandat", "points": [
            ctx["mandat"]["type_label"], f"Mandataire : {ctx['mandat']['mandataire_nom']}",
            "Mandat signé" if ctx["mandat"]["signed_by"] else "Mandat non signé"]},
        {"key": "methodologie", "title": "Méthodologie", "points": [
            f"{len(ctx['hypotheses'])} hypothèse(s)", f"{len(ctx['plan'])} action(s) planifiée(s)",
            f"Durée estimée : {ctx['duree_totale']}"]},
        {"key": "analyse", "title": "Analyse des preuves", "points": [
            f"{p['pv_id']} : {p['witness']}" for p in ctx["pvs"]] or ["Aucun PV"]},
        {"key": "resultats", "title": "Résultats techniques", "points": [
            f"{r['rank']}. {r['action']} ({r['score_txt']})" for r in ctx["rapports"]] or ["Aucun rapport technique"]},
        {"key": "conclusion", "title": "Conclusion et recommandations", "points": [
            "Conclusion de l'expert renseignée" if ctx["conclusion"] else "Conclusion à renseigner",
            f"{len(ctx['recommandations'])} recommandation(s) automatique(s)"]},
        {"key": "custody", "title": "Chaîne de custody", "points": [
            f"Intégrité du journal : {ctx['chain_status']}", f"{ctx['chain_entries']} entrées au total"]},
    ]


def _context(db: Session, case, expert: Expert, body: GenerateIn, version: int) -> dict:
    pvs = _case_pvs(db, case.id)
    if not pvs:
        raise HTTPException(409, "Analysez au moins un PV avant de générer le rapport")
    incs = detect(_all_facts(pvs))
    method = build_methodology(case.case_type, incs)
    tech = analysis_for_case(db, case)
    signature = db.get(MandateSignature, case.id)
    contract = db.scalars(select(Contract).where(Contract.case_id == case.id)
                          .order_by(Contract.generated_at.desc()).limit(1)).first()
    audit_rows = db.scalars(select(AuditLog).where(AuditLog.case_id == case.id).order_by(AuditLog.id)).all()
    chain = verify_chain(db)
    now = datetime.now(timezone.utc)
    pv_items, hashes = [], []
    for p in pvs:
        ent = json.loads(p.analysis)["entities"]
        pv_items.append({"pv_id": p.pv_id, "witness": p.witness_name, "personnes": ent["personnes"],
                         "lieux": ent["lieux"], "dates": ent["dates"], "montants": ent["montants"]})
        hashes.append({"name": f"PV {p.pv_id}", "sha256": p.sha256})
    if contract:
        hashes.append({"name": "Contrat", "sha256": contract.hash_sha256})
    high = sum(1 for i in incs if i["severity"] == "haute")
    ctx = {
        "date": now.strftime("%d/%m/%Y"), "version": version,
        "mandat": {"case_id": case.id, "type_label": CASE_LABEL.get(case.case_type, case.case_type),
                   "priority": case.priority, "description": case.description,
                   "mandataire_nom": case.mandataire_nom, "mandataire_fonction": case.mandataire_fonction,
                   "signed_by": signature.signed_by if signature else None,
                   "signed_at": signature.signed_at if signature else None},
        "expert": {"nom": expert.nom},
        "contract": {"sha256": contract.hash_sha256} if contract else None,
        "pvs": pv_items,
        "incoherences": [{**i, "type_label": TYPE_LABEL[i["type"]]} for i in incs],
        "high_count": high, "coherence_pct": round(max(0.0, 1 - 0.2 * len(incs)) * 100),
        "hypotheses": method["hypotheses"], "plan": method["plan"], "duree_totale": method["duree_totale_estimee"],
        "rapports": [{**r, "score_txt": f"{r['score']:.2f}"} for r in tech["rapports"]],
        "chain": [c["action"] for c in tech["chaine_optimale"]],
        "score_global": "non calculé" if tech["score_global"] is None else f"{tech['score_global']:.2f}",
        "recommandations": tech["recommandations"], "conclusion": body.conclusion.strip(),
        "audit": [{"timestamp": a.timestamp, "module": a.module, "action": a.action, "user": a.user or "systeme",
                   "hash": (a.file_hash or a.entry_hash)[:12]} for a in audit_rows[-MAX_AUDIT_ROWS:]],
        "chain_status": "valide" if chain["valid"] else "ALTÉRÉ", "chain_entries": chain["entries"],
        "pseudonymized": body.pseudonymize, "hashes": hashes,
    }
    if body.pseudonymize:
        ctx = _mask(ctx, _pseudonymizer(pvs))
    return ctx


@router.post("/generate", status_code=201)
def generate(body: GenerateIn, user: User = Depends(require_role("investigateur")), db: Session = Depends(get_db)):
    case = case_for(db, body.case_id, user, "mission")
    expert = db.get(Expert, case.chosen_expert_id)
    last = db.scalars(select(FinalReport).where(FinalReport.case_id == case.id)
                      .order_by(FinalReport.version.desc()).limit(1)).first()
    version = (last.version if last else 0) + 1
    ctx = _context(db, case, expert, body, version)
    rid = str(uuid.uuid4())
    try:
        pdf = render_pdf("rapport.tex.j2", ctx, output_dir() / "reports" / case.id / rid, "rapport")
    except LatexError as e:
        log_action(db, "I", "generate_report_failed", case_id=case.id, user=user.email, data={"error": str(e)[:300]})
        raise HTTPException(500, "Report generation failed") from e
    row = FinalReport(id=rid, case_id=case.id, version=version, pdf_path=str(pdf), sha256=sha256_file(str(pdf)),
                      generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                      generated_by=user.email, pseudonymized=body.pseudonymize, outline=json.dumps(_outline(ctx)))
    db.add(row)
    db.commit()
    log_action(db, "I", "generate_report", case_id=case.id, user=user.email, file_path=str(pdf),
               data={"version": version, "pseudonymized": body.pseudonymize})
    return _ser(row)


@router.get("")
def list_reports(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """All versions of the final report, newest first (visible to the mandataire and the investigator)."""
    case_for(db, case_id, user, "view")
    rows = db.scalars(select(FinalReport).where(FinalReport.case_id == case_id)
                      .order_by(FinalReport.version.desc())).all()
    return {"case_id": case_id, "reports": [_ser(r) for r in rows]}


@router.get("/{report_id}/download")
def download(report_id: str, encoding: Encoding = "raw", user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(FinalReport, report_id)
    if not r or not Path(r.pdf_path).is_file():
        raise HTTPException(404, "Report not found")
    case_for(db, r.case_id, user, "view")
    if sha256_file(r.pdf_path) != r.sha256:
        raise HTTPException(409, "Integrity check failed: the stored report was modified")
    return file_answer(r.pdf_path, "application/pdf", f"rapport_v{r.version}.pdf", encoding)
