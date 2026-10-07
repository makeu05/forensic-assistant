import smtplib
import socket
from pathlib import Path

import pytest
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword

from app.core import mail
from app.core.config import load_env, parse

LOGIN, KEY = "1a2b3c@smtp-brevo.com", "xsmtpsib-test-key"


class FakeRelay:
    """A real SMTP server on localhost that demands a login, like a relay provider does."""

    def __init__(self):
        self.messages, self.login_attempts = [], 0

    async def handle_DATA(self, server, session, envelope):
        self.messages.append(envelope)
        return "250 Message accepted"

    def authenticator(self, server, session, envelope, mechanism, auth_data):
        self.login_attempts += 1
        ok = isinstance(auth_data, LoginPassword) and auth_data.login == LOGIN.encode() and auth_data.password == KEY.encode()
        return AuthResult(success=ok, handled=False)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def relay(monkeypatch):
    handler, port = FakeRelay(), _free_port()
    controller = Controller(handler, hostname="127.0.0.1", port=port, authenticator=handler.authenticator,
                            auth_required=True, auth_require_tls=False)
    controller.start()
    for k, v in {"SMTP_HOST": "127.0.0.1", "SMTP_PORT": str(port), "SMTP_USER": LOGIN, "SMTP_PASSWORD": KEY,
                 "SMTP_FROM": "locard@example.org", "SMTP_STARTTLS": "false"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(mail.time, "sleep", lambda _: None)
    yield handler
    controller.stop()


# ---------------------------------------------------------------- .env loading

def test_parse_handles_comments_quotes_and_inline_comments():
    text = """
# a comment
JWT_SECRET=abc123
export SMTP_HOST = smtp-relay.brevo.com
SMTP_USER=
SMTP_FROM="Locard <no-reply@example.org>"
APP_NAME='my app'
SMTP_PORT=587   # the submission port
not a valid line
"""
    assert parse(text) == {"JWT_SECRET": "abc123", "SMTP_HOST": "smtp-relay.brevo.com", "SMTP_USER": "",
                           "SMTP_FROM": "Locard <no-reply@example.org>", "APP_NAME": "my app", "SMTP_PORT": "587"}


def test_blank_value_with_a_trailing_comment_stays_blank():
    assert parse("SMTP_USER=      # the login from Brevo") == {"SMTP_USER": ""}


def test_env_file_never_overrides_the_real_environment(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("LOCARD_TEST_A=from-file\nLOCARD_TEST_B=from-file\n", encoding="utf-8")
    monkeypatch.delenv("LOCARD_NO_DOTENV", raising=False)
    monkeypatch.setenv("LOCARD_TEST_A", "from-shell")
    monkeypatch.delenv("LOCARD_TEST_B", raising=False)
    try:
        assert load_env(f) == ["LOCARD_TEST_B"]  # reports names only, never values
        import os
        assert os.environ["LOCARD_TEST_A"] == "from-shell" and os.environ["LOCARD_TEST_B"] == "from-file"
    finally:
        import os
        os.environ.pop("LOCARD_TEST_B", None)


def test_env_file_is_skipped_when_disabled(tmp_path):
    f = tmp_path / ".env"
    f.write_text("LOCARD_TEST_C=x\n", encoding="utf-8")
    assert load_env(f) == []  # conftest sets LOCARD_NO_DOTENV for the whole suite


def test_env_files_are_git_ignored():
    ignore = (Path(__file__).parent.parent / ".gitignore").read_text()
    assert ".env" in ignore.splitlines() and "!.env.example" in ignore.splitlines()


# ------------------------------------------------------------------ delivery

def test_settings_summary_never_contains_the_password(relay):
    cfg = mail.smtp_settings()
    assert cfg["has_password"] is True and KEY not in str(cfg)


def test_message_is_delivered_through_an_authenticated_relay(relay):
    assert mail.deliver("expert@cabinet-dubois.fr", "Locard : test", "Bonjour,\nLien : http://x/activate?token=abc\n") == "smtp"
    assert len(relay.messages) == 1
    env = relay.messages[0]
    assert env.rcpt_tos == ["expert@cabinet-dubois.fr"] and env.mail_from == "locard@example.org"
    raw = env.content.decode("utf8", "replace")
    assert "Subject: Locard : test" in raw and "From: Locard <locard@example.org>" in raw


def test_wrong_key_is_reported_and_not_retried(relay, monkeypatch):
    monkeypatch.setenv("SMTP_PASSWORD", "wrong-key")
    real, connections = mail._open_smtp, {"n": 0}

    def counting():
        connections["n"] += 1
        return real()

    monkeypatch.setattr(mail, "_open_smtp", counting)
    with pytest.raises(smtplib.SMTPAuthenticationError):
        mail.deliver("a@bureau.fr", "s", "b")
    # one connection only: a wrong key is not a network hiccup, retrying cannot help.
    # (smtplib itself tries several login methods inside that one connection.)
    assert connections["n"] == 1 and relay.messages == []


def test_network_hiccup_is_retried_once(relay, monkeypatch):
    real, calls = mail._open_smtp, {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise smtplib.SMTPServerDisconnected("connection dropped")
        return real()

    monkeypatch.setattr(mail, "_open_smtp", flaky)
    assert mail.deliver("a@bureau.fr", "s", "b") == "smtp"
    assert calls["n"] == 2 and len(relay.messages) == 1


def test_a_server_that_stays_down_fails_after_two_attempts(relay, monkeypatch):
    calls = {"n": 0}

    def down():
        calls["n"] += 1
        raise ConnectionRefusedError("nothing listens")

    monkeypatch.setattr(mail, "_open_smtp", down)
    with pytest.raises(ConnectionRefusedError):
        mail.deliver("a@bureau.fr", "s", "b")
    assert calls["n"] == mail.ATTEMPTS


def test_sender_is_required_when_a_relay_is_configured(relay, monkeypatch):
    monkeypatch.setenv("SMTP_FROM", "")
    with pytest.raises(mail.MailConfigError, match="SMTP_FROM"):
        mail.deliver("a@bureau.fr", "s", "b")


def test_login_without_password_is_a_clear_error(relay, monkeypatch):
    monkeypatch.setenv("SMTP_PASSWORD", "")
    with pytest.raises(mail.MailConfigError, match="SMTP_PASSWORD"):
        mail.deliver("a@bureau.fr", "s", "b")


def test_send_email_never_raises_inside_a_request(relay, monkeypatch):
    monkeypatch.setenv("SMTP_PASSWORD", "wrong-key")
    assert mail.send_email("a@bureau.fr", "s", "b") == "failed"


def test_header_injection_is_refused(relay):
    assert mail.send_email("a@bureau.fr", "Hello\r\nBcc: evil@example.org", "body") == "failed"
    assert mail.send_email("a@bureau.fr\r\nBcc: evil@example.org", "Hello", "body") == "failed"
    assert relay.messages == []


# ---------------------------------------------------------- connection check

def test_check_connection_logs_in_without_sending(relay):
    assert "logged in as" in mail.check_connection()
    assert relay.messages == [] and relay.login_attempts >= 1


def test_check_connection_reports_a_bad_login(relay, monkeypatch):
    monkeypatch.setenv("SMTP_USER", "someone-else@smtp-brevo.com")
    with pytest.raises(smtplib.SMTPAuthenticationError):
        mail.check_connection()


def test_check_connection_when_unconfigured(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "")
    with pytest.raises(mail.MailConfigError, match="local outbox"):
        mail.check_connection()


def test_unconfigured_mail_goes_to_the_local_outbox(monkeypatch, tmp_path):
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    path = Path(mail.deliver("a@bureau.fr", "Sujet", "Corps"))
    assert path.parent == tmp_path / "outbox" and b"Subject: Sujet" in path.read_bytes()


# ------------------------------------------------- never send to undeliverable addresses

@pytest.mark.parametrize("address", [
    "alice.dubois0@experts.example", "someone@company.test", "x@bad.invalid", "x@host.localhost",
    "x@example.com", "x@EXAMPLE.org", "Alice <alice@experts.example>",
])
def test_reserved_domains_are_never_sent_for_real(relay, monkeypatch, tmp_path, address):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    result = mail.deliver(address, "Sujet", "Corps")
    assert result != "smtp" and Path(result).parent == tmp_path / "outbox"
    assert relay.messages == [] and relay.login_attempts == 0  # not even a connection to the provider


@pytest.mark.parametrize("address", ["claire@gmail.com", "marc@tribunal-lyon.fr", "Marc Dupont <marc@cabinet.com>"])
def test_real_domains_are_sent(relay, address):
    assert mail.deliver(address, "Sujet", "Corps") == "smtp" and len(relay.messages) == 1


def test_allow_list_restricts_real_sending(relay, monkeypatch, tmp_path):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("SMTP_ALLOWED", "belvarose150@gmail.com, @cabinet-dubois.fr")
    assert mail.deliver("belvarose150@gmail.com", "s", "b") == "smtp"
    assert mail.deliver("expert@cabinet-dubois.fr", "s", "b") == "smtp"
    assert mail.deliver("sous@equipe.cabinet-dubois.fr", "s", "b") == "smtp"  # subdomain of an allowed domain
    held = mail.deliver("stranger@gmail.com", "s", "b")
    assert held != "smtp" and Path(held).parent == tmp_path / "outbox"
    assert len(relay.messages) == 3


def test_hold_reason_explains_itself(monkeypatch):
    monkeypatch.delenv("SMTP_ALLOWED", raising=False)
    assert "reserved domain" in mail.hold_reason("a@experts.example")
    assert mail.hold_reason("a@gmail.com") is None
    assert mail.hold_reason("not-an-address") == "the address is not valid"
    monkeypatch.setenv("SMTP_ALLOWED", "only@me.fr")
    assert mail.hold_reason("a@gmail.com") == "the address is not in SMTP_ALLOWED"


def test_seeded_experts_can_never_receive_real_mail():
    from app.modules.matching.seed import PROFILES, FIRST, LAST  # noqa: F401
    assert mail.hold_reason("ivan.mbarga8@experts.example") is not None
