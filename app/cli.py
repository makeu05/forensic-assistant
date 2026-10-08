"""Administration commands.

    python -m app.cli create-user --email you@example.com --name "Your Name" --role mandataire
    python -m app.cli create-user --email a@b.c --name "A B" --role investigateur --expert-id 12
    python -m app.cli list-experts --search dubois
    python -m app.cli rotate-logs --max-mb 100
    python -m app.cli import-experts experts.csv          (dry run; add --apply)
    python -m app.cli remove-demo-experts                 (dry run; add --apply)
    python -m app.cli purge-expired --months 6          (dry run; add --apply to delete)
    python -m app.cli check-mail
    python -m app.cli send-test-mail --to someone@example.com

Mail settings come from the environment or the git-ignored `.env` file (copy `.env.example`).
check-mail tests the connection and login without sending anything; send-test-mail sends one real message.
Without SMTP_HOST, mail only goes to the local outbox.

The password is asked on the terminal (never passed as an argument, so it stays out of shell history).
Investigators normally join through the invitation email; this is for administrators.
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import select

from app.modules.audit.service import _log_path, rotate_log
from app.core.mail import check_connection, deliver, hold_reason, smtp_settings, test_mail
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


def check_mail(_: argparse.Namespace) -> int:
    cfg = smtp_settings()
    print("Mail settings (the password is never shown):")
    print(f"  host     : {cfg['host'] or '(not set: mail stays in the local outbox)'}")
    print(f"  port     : {cfg['port']}   starttls: {cfg['starttls']}")
    print(f"  login    : {cfg['user'] or '(none)'}   password set: {cfg['has_password']}")
    print(f"  sender   : {cfg['sender'] or '(not set)'}")
    try:
        print(check_connection())
    except Exception as e:  # noqa: BLE001 - show the reason, that is the point
        print(f"Check failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print("The server accepted the login. Nothing was sent. Next: python -m app.cli send-test-mail --to you@example.com")
    return 0


def rotate_logs(args: argparse.Namespace) -> int:
    path = _log_path()
    archive = rotate_log(path, int(args.max_mb * 1024 * 1024))
    if archive:
        print(f"Archived {path.name} to {archive.name}. The new file starts with a marker holding the archive's SHA-256.")
    else:
        size = path.stat().st_size if path.exists() else 0
        print(f"No rotation needed: {path} is {size / 1048576:.2f} MB (limit {args.max_mb} MB). Use --max-mb 0 to force it.")
    return 0


def purge_expired(args: argparse.Namespace) -> int:
    from app.modules.privacy.retention import purge

    with SessionLocal() as db:
        found = purge(db, args.months, apply=args.apply)
    if not found:
        print(f"Nothing to purge: no mission ended more than {args.months:g} months ago still holds interview data.")
        return 0
    verb = "Deleted" if args.apply else "Would delete"
    for item in found:
        print(f"{verb} for case {item.case_id[:8]} (report of {item.report_at[:10]}): "
              f"{item.pvs} PV, {item.tech_reports} technical report(s), {len(item.files)} file(s)/folder(s)")
    if not args.apply:
        print("Dry run: nothing was changed. Add --apply to delete. The audit trail is never touched.")
    return 0


def import_experts_cmd(args: argparse.Namespace) -> int:
    from pathlib import Path

    from app.modules.matching.importer import import_experts, parse_csv

    path = Path(args.csv)
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 1
    result = parse_csv(path.read_text(encoding="utf-8-sig"))
    for problem in result.errors:
        print(f"  ! {problem}", file=sys.stderr)
    if result.errors and not args.partial:
        print("Nothing imported: fix the lines above, or use --partial to import the valid ones.", file=sys.stderr)
        return 1
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        result = import_experts(db, result, apply=args.apply)
    verb = "Imported" if args.apply else "Would import"
    print(f"{verb} {len(result.rows)} expert(s); {len(result.skipped)} already in the base; {len(result.errors)} invalid line(s).")
    if not args.apply:
        print("Dry run: add --apply to write them.")
    return 0


def remove_demo(args: argparse.Namespace) -> int:
    from app.modules.matching.importer import remove_demo_experts

    with SessionLocal() as db:
        removed = remove_demo_experts(db, apply=args.apply)
    verb = "Removed" if args.apply else "Would remove"
    print(f"{verb} {len(removed)} demo expert(s) (@experts.example) that no account or request refers to.")
    if not args.apply:
        print("Dry run: add --apply to delete them.")
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
        why = "SMTP_HOST is not set" if not smtp_settings()["configured"] else (hold_reason(args.to) or "held")
        print(f"Nothing was sent ({why}). The message was written to {result}.")
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
    r = sub.add_parser("rotate-logs")
    r.add_argument("--max-mb", type=float, default=100.0)
    r.set_defaults(run=rotate_logs)
    ie = sub.add_parser("import-experts")
    ie.add_argument("csv")
    ie.add_argument("--apply", action="store_true", help="really write (default is a dry run)")
    ie.add_argument("--partial", action="store_true", help="import the valid lines even if some are invalid")
    ie.set_defaults(run=import_experts_cmd)
    rd = sub.add_parser("remove-demo-experts")
    rd.add_argument("--apply", action="store_true", help="really delete (default is a dry run)")
    rd.set_defaults(run=remove_demo)
    pg = sub.add_parser("purge-expired")
    pg.add_argument("--months", type=float, default=6.0)
    pg.add_argument("--apply", action="store_true", help="really delete (default is a dry run)")
    pg.set_defaults(run=purge_expired)
    sub.add_parser("check-mail").set_defaults(run=check_mail)
    t = sub.add_parser("send-test-mail")
    t.add_argument("--to", required=True)
    t.set_defaults(run=send_test)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
