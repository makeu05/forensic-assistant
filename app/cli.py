"""Administration commands.

    python -m app.cli create-user --email you@example.com --name "Your Name" --role mandataire
    python -m app.cli create-user --email a@b.c --name "A B" --role investigateur --expert-id 12
    python -m app.cli list-experts --search dubois
    python -m app.cli send-test-mail --to someone@example.com

send-test-mail uses the SMTP_* environment variables (see app/core/mail.py). Without SMTP_HOST it only
writes the message to the local outbox. Typical Gmail setup, typed in your own terminal (never in a file):
    $env:SMTP_HOST="smtp.gmail.com"; $env:SMTP_PORT="587"; $env:SMTP_USER="you@gmail.com"
    $env:SMTP_PASSWORD="<16-character app password>"; $env:SMTP_FROM="you@gmail.com"

The password is asked on the terminal (never passed as an argument, so it stays out of shell history).
Investigators normally join through the invitation email; this is for administrators.
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import select

from app.core.mail import deliver, test_mail
from app.db import Base, SessionLocal, engine, ensure_columns
from app.modules.auth import invitations  # noqa: F401  (registers the invitations table)
from app.modules.auth.service import ROLES, create_user, get_user_by_email
from app.modules.cases import router as _cases  # noqa: F401
from app.modules.matching.service import Expert


def create(args: argparse.Namespace) -> int:
    Base.metadata.create_all(engine)
    ensure_columns(engine)
    password = getpass.getpass("Password (12 characters minimum): ")
    if len(password) < 12 or len(password) > 128:
        print("Password must be 12 to 128 characters.", file=sys.stderr)
        return 1
    if password != getpass.getpass("Repeat password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        if get_user_by_email(db, args.email):
            print("An account with this email already exists.", file=sys.stderr)
            return 1
        if args.role == "investigateur":
            if args.expert_id is None or db.get(Expert, args.expert_id) is None:
                print("An investigator needs a valid --expert-id (see list-experts).", file=sys.stderr)
                return 1
        user = create_user(db, args.email, args.name, password, args.role,
                           args.expert_id if args.role == "investigateur" else None)
        print(f"Created {user.role} {user.email} (id {user.id}).")
    return 0


def list_experts(args: argparse.Namespace) -> int:
    with SessionLocal() as db:
        query = select(Expert).order_by(Expert.id)
        for e in db.scalars(query):
            if args.search and args.search.lower() not in f"{e.nom} {e.email}".lower():
                continue
            print(f"{e.id:>4}  {e.nom:<24} {e.email}")
    return 0


def send_test(args: argparse.Namespace) -> int:
    subject, body = test_mail()
    try:
        result = deliver(args.to, subject, body)
    except Exception as e:  # noqa: BLE001 - the point of this command is to show the reason
        print(f"Sending failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if result == "smtp":
        print(f"Sent to {args.to} through {os.environ['SMTP_HOST']}.")
    else:
        print(f"SMTP_HOST is not set, so nothing was sent. The message was written to {result}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("create-user")
    c.add_argument("--email", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--role", required=True, choices=ROLES)
    c.add_argument("--expert-id", type=int)
    c.set_defaults(run=create)
    ls = sub.add_parser("list-experts")
    ls.add_argument("--search")
    ls.set_defaults(run=list_experts)
    t = sub.add_parser("send-test-mail")
    t.add_argument("--to", required=True)
    t.set_defaults(run=send_test)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
