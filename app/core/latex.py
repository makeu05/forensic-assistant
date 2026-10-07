"""Shared LaTeX rendering: Jinja2 templating with escaping, then pdflatex."""
import os
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
LATEX_TIMEOUT = int(os.getenv("LATEX_TIMEOUT", "60"))

_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def tex(value) -> str:
    """Escape user text so it can never inject LaTeX commands."""
    return "".join(_SPECIALS.get(ch, ch) for ch in str(value if value is not None else ""))


# Custom delimiters so Jinja never collides with LaTeX braces.
_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    block_start_string="<%", block_end_string="%>",
    variable_start_string="<<", variable_end_string=">>",
    comment_start_string="<#", comment_end_string="#>",
    autoescape=False, trim_blocks=True, lstrip_blocks=True,
)
_env.filters["tex"] = tex


class LatexError(RuntimeError):
    pass


def render_pdf(template: str, context: dict, out_dir: Path, name: str) -> Path:
    """Render template with context and compile to out_dir/name.pdf."""
    if shutil.which("pdflatex") is None:
        raise LatexError("pdflatex is not installed")
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    tex_path = out_dir / f"{name}.tex"
    tex_path.write_text(_env.get_template(template).render(**context), encoding="utf-8")
    try:
        proc = subprocess.run(
            ["pdflatex", "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error",
             f"-output-directory={out_dir}", str(tex_path)],
            capture_output=True, timeout=LATEX_TIMEOUT, cwd=out_dir,
        )
    except subprocess.TimeoutExpired as e:
        raise LatexError(f"pdflatex timed out after {LATEX_TIMEOUT}s") from e
    pdf = out_dir / f"{name}.pdf"
    if proc.returncode != 0 or not pdf.exists():
        log = out_dir / f"{name}.log"
        lines = log.read_text(errors="replace").splitlines() if log.exists() else []
        first = next((ln for ln in lines if ln.startswith("!")), "unknown error")
        raise LatexError(f"LaTeX compilation failed: {first}")
    for ext in ("aux", "log"):
        (out_dir / f"{name}.{ext}").unlink(missing_ok=True)
    return pdf
