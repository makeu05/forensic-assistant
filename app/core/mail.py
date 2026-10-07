"""Outgoing email for Locard.

With SMTP_HOST set, mail goes out over SMTP (STARTTLS on port 587 by default), for example through
Brevo (smtp-relay.brevo.com). Without it, every message is written as an .eml file under
OUTPUT_DIR/outbox, so development and tests never send real mail by accident.

Environment: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_STARTTLS (true/false),
APP_BASE_URL (used to build links, default http://localhost:5173). They can live in the git-ignored
`.env` file (see .env.example).
"""
import logging
import os
import smtplib
import time
import uuid
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
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


class MailConfigError(RuntimeError):
    """The SMTP settings are incomplete or inconsistent."""


# Network hiccups worth one retry. Wrong password, refused recipient, etc. are not: retrying cannot fix them.
TRANSIENT = (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, ConnectionError, TimeoutError)
ATTEMPTS = 2


def smtp_settings() -> dict:
    """The current SMTP settings, safe to print: the password is never included."""
    host = os.getenv("SMTP_HOST", "").strip()
    return {
        "configured": bool(host), "host": host, "port": int(os.getenv("SMTP_PORT") or "587"),
        "user": os.getenv("SMTP_USER", ""), "sender": os.getenv("SMTP_FROM", ""),
        "starttls": os.getenv("SMTP_STARTTLS", "true").lower() != "false",
        "has_password": bool(os.getenv("SMTP_PASSWORD")),
    }


def _open_smtp() -> smtplib.SMTP:
    """A connected, TLS-secured, logged-in SMTP session. The caller closes it."""
    cfg = smtp_settings()
    if cfg["user"] and not cfg["has_password"]:
        raise MailConfigError("SMTP_USER is set but SMTP_PASSWORD is empty.")
    smtp = smtplib.SMTP(cfg["host"], cfg["port"], timeout=15)
    try:
        if cfg["starttls"]:
            smtp.starttls()
        if cfg["user"]:
            smtp.login(cfg["user"], os.environ["SMTP_PASSWORD"])
    except Exception:
        smtp.close()
        raise
    return smtp


def check_connection() -> str:
    """Connect, secure the channel and log in, without sending anything. Raises with the reason on failure."""
    cfg = smtp_settings()
    if not cfg["configured"]:
        raise MailConfigError("SMTP_HOST is not set: mail only goes to the local outbox.")
    smtp = _open_smtp()
    try:
        smtp.noop()
    finally:
        smtp.quit()
    return f"Connected to {cfg['host']}:{cfg['port']}" + (f" and logged in as {cfg['user']}" if cfg["user"] else "")


# Reserved names (RFC 2606 / 6761) that can never receive mail. Sending to them only creates bounces,
# which damage the sender's reputation with the provider, so they are never sent for real.
UNDELIVERABLE_TLDS = {"example", "test", "invalid", "localhost", "local"}
UNDELIVERABLE_DOMAINS = {"example.com", "example.org", "example.net"}


def _domain(address: str) -> str:
    return parseaddr(address)[1].rsplit("@", 1)[-1].strip().lower()


def hold_reason(address: str) -> str | None:
    """Why this address must not receive real mail, or None if it may. Held mail goes to the local outbox.

    1. Reserved, undeliverable domains (experts.example, anything.test, example.com...) are always held.
    2. If SMTP_ALLOWED is set (comma-separated addresses or domains, e.g. "me@gmail.com, mydomain.fr"),
       only matching recipients are sent for real.
    """
    domain = _domain(address)
    if not domain or "." not in domain and domain not in UNDELIVERABLE_TLDS:
        return "the address is not valid"
    if domain in UNDELIVERABLE_DOMAINS or domain.rsplit(".", 1)[-1] in UNDELIVERABLE_TLDS:
        return f"{domain} is a reserved domain that cannot receive mail"
    allowed = [a.strip().lower().lstrip("@") for a in os.getenv("SMTP_ALLOWED", "").split(",") if a.strip()]
    if allowed and not any(parseaddr(address)[1].lower() == a or domain == a or domain.endswith("." + a) for a in allowed):
        return "the address is not in SMTP_ALLOWED"
    return None


def _to_outbox(msg: EmailMessage) -> str:
    folder = outbox_dir()
    folder.mkdir(parents=True, exist_ok=True)
    # nanosecond clock first, so a directory listing is in sending order
    path = folder / f"{time.time_ns()}_{uuid.uuid4().hex[:6]}.eml"
    path.write_bytes(bytes(msg))
    return str(path)


def deliver(to: str, subject: str, body: str) -> str:
    """Send one message and let any error propagate. Returns "smtp" or the path of the .eml written."""
    msg = build_message(to, subject, body)
    cfg = smtp_settings()
    if not cfg["configured"]:
        return _to_outbox(msg)
    if (reason := hold_reason(to)) is not None:
        log.info("Mail to %s held in the outbox: %s", to, reason)
        return _to_outbox(msg)
    if not cfg["sender"]:
        raise MailConfigError("SMTP_FROM is required when SMTP_HOST is set (use a sender verified with your provider).")
    for attempt in range(1, ATTEMPTS + 1):
        try:
            smtp = _open_smtp()
            try:
                smtp.send_message(msg)
            finally:
                smtp.quit()
            return "smtp"
        except TRANSIENT as e:
            if attempt == ATTEMPTS:
                raise
            log.warning("Mail attempt %d failed (%s), retrying", attempt, type(e).__name__)
            time.sleep(attempt)
    return "smtp"  # unreachable, keeps the type checker content


def send_email(to: str, subject: str, body: str) -> str:
    """deliver() for use inside requests: a mail failure must not break the request that triggered it,
    so it is logged and "failed" is returned instead of raising."""
    try:
        return deliver(to, subject, body)
    except Exception:  # noqa: BLE001 - deliberately broad, see docstring
        log.exception("Could not send email to %s", to)
        return "failed"


# ---------------------------------------------------------------- message texts (French)

def invitation_mail(name: str, case_type: str, priority: str, link: str) -> tuple[str, str]:
    return ("Locard : invitation à rejoindre la plateforme", (
        f"Bonjour {name},\n\n"
        "Un mandataire vous a sollicité(e) pour une mission d'investigation numérique sur Locard "
        f"(type : {case_type}, priorité : {priority}).\n\n"
        "Pour consulter la demande et y répondre, créez votre compte avec ce lien personnel. "
        "Il est valable 7 jours et ne peut servir qu'une seule fois :\n\n"
        f"{link}\n\n"
        "Si vous n'êtes pas concerné(e), ignorez simplement ce message : aucun compte ne sera créé.\n\n"
        "Locard\n"))


def request_mail(name: str, case_type: str, priority: str) -> tuple[str, str]:
    return ("Locard : nouvelle demande de mission", (
        f"Bonjour {name},\n\n"
        f"Vous avez reçu une nouvelle demande de mission (type : {case_type}, priorité : {priority}).\n"
        f"Connectez-vous pour l'accepter ou la refuser : {base_url()}\n\n"
        "Locard\n"))


def welcome_mail(name: str, email: str) -> tuple[str, str]:
    return ("Locard : votre compte est actif", (
        f"Bonjour {name},\n\n"
        "Votre inscription sur Locard est confirmée. "
        f"Vous pouvez vous connecter avec l'adresse {email} : {base_url()}\n\n"
        "Si vous n'êtes pas à l'origine de cette inscription, contactez immédiatement l'administrateur.\n\n"
        "Locard\n"))


def test_mail() -> tuple[str, str]:
    return ("Locard : message de test", (
        "Bonjour,\n\n"
        "Ceci est un message de test envoyé par Locard pour vérifier que l'envoi d'e-mails fonctionne.\n"
        "Il ne contient aucune donnée de dossier. Vous pouvez l'ignorer.\n\n"
        "Locard\n"))
