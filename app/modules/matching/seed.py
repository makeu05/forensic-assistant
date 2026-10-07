"""Deterministic seed of 60 expert profiles (spec: 50-100)."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.matching.service import Expert

PROFILES = [
    (["forensic_bancaire", "analyse_logs", "fraude"], "Specialiste fraude bancaire et analyse de virements suspects, correlation de logs transactionnels."),
    (["forensic_reseau", "intrusion", "analyse_reseau"], "Investigation d'intrusions reseau, analyse de trafic, logs firewall et IDS."),
    (["malware", "ransomware", "reverse_engineering"], "Analyse de malware et ransomware, comportement en sandbox, indicateurs de compromission."),
    (["disk_forensic", "analyse_disque", "timeline"], "Forensic disque, recuperation de fichiers supprimes, reconstruction de timeline."),
    (["mobile", "forensic_mobile", "messagerie"], "Forensic mobile, extraction et analyse de messageries et applications."),
    (["cloud", "analyse_logs", "incident_response"], "Reponse a incident cloud, analyse de journaux et exfiltration de donnees."),
    (["cybercriminalite", "enquete", "audition"], "Appui aux enquetes de cybercriminalite, conduite d'auditions et procedure judiciaire."),
    (["vol_donnees", "exfiltration", "analyse_reseau"], "Detection de vol et exfiltration de donnees, analyse de flux sortants."),
]
FIRST = ["Alice", "Bob", "Charlie", "Diane", "Emile", "Fatou", "Gabriel", "Hana", "Ivan", "Jade",
         "Karim", "Lea", "Mamadou", "Nadia", "Oscar", "Paul", "Quentin", "Rose", "Samuel", "Tania"]
LAST = ["Dubois", "Martin", "Leroy", "Mbarga", "Nguyen"]


def seed_experts(db: Session) -> int:
    if db.scalar(select(func.count()).select_from(Expert)):
        return 0
    n = 0
    for i in range(60):
        skills, bio = PROFILES[i % len(PROFILES)]
        first, last = FIRST[i % len(FIRST)], LAST[(i // len(FIRST) + i) % len(LAST)]
        db.add(Expert(
            nom=f"{first} {last}",
            email=f"{first.lower()}.{last.lower()}{i}@experts.example",
            competences=skills,
            bio=bio,
            annees_experience=2 + (i * 7) % 19,
            disponibilite=(i % 4 != 3),
        ))
        n += 1
    db.commit()
    return n
