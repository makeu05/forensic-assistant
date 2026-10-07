"""Reads the project's `.env` file into the environment, once, before anything else reads settings.

Rules, chosen so that a secret can never be loaded by accident:
- A variable that is already set in the real environment always wins over the file.
- Setting LOCARD_NO_DOTENV=1 skips the file entirely (the test suite does this, so a developer's
  real SMTP credentials can never make a test send mail).
- The file is `.env` at the project root. It is git-ignored; `.env.example` shows the format.
"""
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def parse(text: str) -> dict[str, str]:
    """KEY=VALUE lines. Blank lines and '#' comments are skipped, matching quotes around a value are removed."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip().removeprefix("export ").strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            value = re.split(r"(?:^|\s+)#", value, maxsplit=1)[0].strip()  # unquoted: a "# comment" ends the value
        if key.isidentifier():
            values[key] = value
    return values


def load_env(path: Path | None = None) -> list[str]:
    """Load the .env file. Returns the names of the variables it set (never their values)."""
    if os.getenv("LOCARD_NO_DOTENV"):
        return []
    file = path or PROJECT_ROOT / ".env"
    if not file.is_file():
        return []
    loaded = []
    for key, value in parse(file.read_text(encoding="utf-8")).items():
        if key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
