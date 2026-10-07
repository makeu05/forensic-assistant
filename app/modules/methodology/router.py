"""Module G: investigation hypotheses and the forensic methodology plan.

Hypotheses are leads to verify, never conclusions. Each one says what triggered it, so the
investigator can see why it is proposed. The plan orders the forensic actions by how many
hypotheses need them, and sums the duration estimates of the knowledge base.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.access import case_for
from app.modules.auth.router import require_role
from app.modules.auth.service import User
from app.modules.pv.router import _all_facts, _case_pvs
from app.modules.pv.rules import detect

router = APIRouter(prefix="/methodology", tags=["G - Methodology"])

# action key -> label, tools, what it does, (min hours, max hours). 12 tools in total.
FORENSIC_TOOLS = {
    "analyse_logs": {"label": "Analyse des journaux", "outils": ["Splunk", "ELK", "grep/awk"],
                     "description": "Corrélation des événements et reconstruction de la chronologie.", "duree": (3, 5)},
    "analyse_reseau": {"label": "Analyse du trafic réseau", "outils": ["Wireshark", "NetworkMiner", "tcpdump"],
                       "description": "Capture et analyse du trafic, détection d'intrusion et d'exfiltration.", "duree": (2, 6)},
    "analyse_disque": {"label": "Analyse de disque", "outils": ["Autopsy", "FTK Imager", "Sleuth Kit"],
                       "description": "Récupération de fichiers supprimés et reconstruction de la chronologie.", "duree": (4, 8)},
    "malware_analysis": {"label": "Analyse de code malveillant", "outils": ["Ghidra", "Cuckoo Sandbox", "IDA Pro"],
                         "description": "Comportement du code en bac à sable et indicateurs de compromission.", "duree": (8, 16)},
}

CASE_HYPOTHESES = {
    "fraude_bancaire": ("fraude_operations", "Opérations frauduleuses sur un compte compromis ou utilisé par un acteur interne",
                        ["analyse_logs", "analyse_disque"]),
    "intrusion_reseau": ("intrusion_systeme", "Intrusion dans le système d'information avec accès non autorisé",
                         ["analyse_logs", "analyse_reseau", "malware_analysis"]),
    "malware": ("infection_malware", "Infection par un code malveillant introduit par une pièce jointe ou un lien",
                ["malware_analysis", "analyse_logs", "analyse_disque"]),
}
INCOHERENCE_HYPOTHESES = {
    "temporelle": ("manipulation_chronologie", "Chronologie des faits modifiée ou mal restituée",
                   ["analyse_logs", "analyse_disque"]),
    "geographique": ("acces_distant_ou_usurpe", "Accès distant ou identifiants usurpés",
                     ["analyse_reseau", "analyse_logs"]),
    "factuelle": ("declaration_inexacte", "Déclaration inexacte ou volontairement erronée d'un témoin",
                  ["analyse_logs"]),
}


def build_methodology(case_type: str, incoherences: list[dict]) -> dict:
    hypotheses = []
    if case_type in CASE_HYPOTHESES:
        hid, label, actions = CASE_HYPOTHESES[case_type]
        hypotheses.append({"id": hid, "label": label, "actions": actions, "origin": "type_dossier",
                           "basis": f"Type de dossier : {case_type.replace('_', ' ')}.", "pv_references": []})
    for kind in ("temporelle", "geographique", "factuelle"):
        matching = [i for i in incoherences if i["type"] == kind]
        if matching:
            hid, label, actions = INCOHERENCE_HYPOTHESES[kind]
            hypotheses.append({
                "id": hid, "label": label, "actions": actions, "origin": "incoherence",
                "basis": f"{len(matching)} incohérence(s) {kind}(s) détectée(s) dans les PV : " + matching[0]["description"],
                "pv_references": sorted({r for i in matching for r in i["pv_references"]})})

    needed: dict[str, list[str]] = {}
    for h in hypotheses:
        for action in h["actions"]:
            needed.setdefault(action, []).append(h["id"])
    first_seen = list(needed)  # ties keep the order in which the hypotheses list their actions
    ordered = sorted(needed, key=lambda a: (-len(needed[a]), first_seen.index(a)))
    plan = []
    for rank, action in enumerate(ordered, start=1):
        tool = FORENSIC_TOOLS[action]
        n = len(needed[action])
        plan.append({
            "priority": rank, "action": action, "label": tool["label"], "outils": tool["outils"],
            "description": tool["description"], "duree_min": tool["duree"][0], "duree_max": tool["duree"][1],
            "duree_estimee": f"{tool['duree'][0]}-{tool['duree'][1]} h", "justified_by": needed[action],
            "why": f"Priorité {rank} : cette action sert {n} hypothèse(s) sur {len(hypotheses)}.",
        })
    lo, hi = sum(p["duree_min"] for p in plan), sum(p["duree_max"] for p in plan)
    return {"hypotheses": hypotheses, "plan": plan, "duree_totale_min": lo, "duree_totale_max": hi,
            "duree_totale_estimee": f"{lo}-{hi} h" if plan else "0 h"}


@router.get("")
def methodology(case_id: str, user: User = Depends(require_role("investigateur")), db: Session = Depends(get_db)):
    case = case_for(db, case_id, user, "mission")
    incs = detect(_all_facts(_case_pvs(db, case.id)))
    return {"case_id": case.id, **build_methodology(case.case_type, incs)}
