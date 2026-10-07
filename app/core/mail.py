"""Outgoing email for Locard.

With SMTP_HOST set, mail goes out over SMTP (STARTTLS on port 587 by default). Without it,
every message is written as an .eml file under OUTPUT_DIR/outbox, so development and tests
never send real mail by accident.

Environment: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_STARTTLS (true/false),
APP_BASE_URL (used to build links, default http://localhost:5173).
"""
import logging
import os
import smtplib
import time
import uuid
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

log = logging.getLogger("mail")

SENDER_NAME = "Locard"


def base_url() -> str:
    return os.getenv("APP_BASE_URL", "http://localhost:5173").rstrip("/")


def outbox_dir() -> Path:
    return Path(os.getenv("OUTPUT_DIR", "output")) / "outbox"


def build_message(to: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()  # raises ValueError if a header contains a newline (header injection)
    msg["From"] = formataddr((SENDER_NAME, os.getenv("SMTP_FROM", "locard@localhost")))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def send_email(to: str, subject: str, body: str) -> str:
    """Send one message. Returns "smtp" or the path of the .eml file written. Never raises:
    a mail failure must not break the request that triggered it, so it is logged instead."""
    try:
        msg = build_message(to, subject, body)
        host = os.getenv("SMTP_HOST")
        if not host:
            folder = outbox_dir()
            folder.mkdir(parents=True, exist_ok=True)
            # nanosecond clock first, so a directory listing is in sending order
            path = folder / f"{time.time_ns()}_{uuid.uuid4().hex[:6]}.eml"
            path.write_bytes(bytes(msg))
            return str(path)
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as smtp:
            if os.getenv("SMTP_STARTTLS", "true").lower() != "false":
                smtp.starttls()
            if os.getenv("SMTP_USER"):
                smtp.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
            smtp.send_message(msg)
        return "smtp"
    except Exception:  # noqa: BLE001 - deliberately broad, see docstring
        log.exception("Could not send email to %s", to)
        return "failed"


# ---------------------------------------------------------------- message texts (French)

def invitation_mail(name: str, case_type: str, priority: str, link: str) -> tuple[str, str]:
    return ("Locard : invitation a rejoindre la plateforme", (
        f"Bonjour {name},\n\n"
        "Un mandataire vous a sollicite(e) pour une mission d'investigation numerique sur Locard "
        f"(type : {case_type}, priorite : {priority}).\n\n"
        "Pour consulter la demande et y repondre, creez votre compte avec ce lien personnel. "
        "Il est valable 7 jours et ne peut servir qu'une seule fois :\n\n"
        f"{link}\n\n"
        "Si vous n'etes pas concerne(e), ignorez simplement ce message : aucun compte ne sera cree.\n\n"
        "Locard\n"))


def request_mail(name: str, case_type: str, priority: str) -> tuple[str, str]:
    return ("Locard : nouvelle demande de mission", (
        f"Bonjour {name},\n\n"
        f"Vous avez recu une nouvelle demande de mission (type : {case_type}, priorite : {priority}).\n"
        f"Connectez-vous pour l'accepter ou la refuser : {base_url()}\n\n"
        "Locard\n"))


def welcome_mail(name: str, email: str) -> tuple[str, str]:
    return ("Locard : votre compte est actif", (
        f"Bonjour {name},\n\n"
        "Votre inscription sur Locard est confirmee. "
        f"Vous pouvez vous connecter avec l'adresse {email} : {base_url()}\n\n"
        "Si vous n'etes pas a l'origine de cette inscription, contactez immediatement l'administrateur.\n\n"
        "Locard\n"))
