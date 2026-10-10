# Locard

**An assistant for digital investigations.** Locard guides a *mandataire* (a judge, a company director, a private person) and an *expert* (the investigator) through a whole mission: the mandate, the choice of an expert, the contract, the preparation of the interviews, the analysis of witness statements, and the final expert report. At every step it keeps a verifiable record of who did what.

The name comes from Locard's exchange principle: *every contact leaves a trace*.

> The interface is in French. This README is in English.

![Locard, analysis of witness statements](docs/screenshots/05-analyse-des-pv.png)

*Two witness statements contradict each other: one authorises a transfer on 10/10/2025, the other says the account was compromised on 05/10/2025. Locard marks the entities in each text, shows both excerpts side by side, and explains why it flagged them.*

---

## Contents

1. [What it does](#what-it-does)
2. [Screenshots](#screenshots)
3. [How it works](#how-it-works)
4. [Run it on your computer](#run-it-on-your-computer)
5. [Settings](#settings)
6. [Administration commands](#administration-commands)
7. [Tests](#tests)
8. [Deploy it](#deploy-it)
9. [Security and data protection](#security-and-data-protection)
10. [Project layout](#project-layout)
11. [What Locard does not do](#what-locard-does-not-do)
12. [More documentation](#more-documentation)

---

## What it does

A case moves through six steps. Each step is done by one of the two roles; the other role can follow along.

| # | Step | Who acts | What happens |
|---|---|---|---|
| 1 | **Mandat** | Mandataire | Creates the mandate: type of case (bank fraud, network intrusion, malware), description, priority. |
| 2 | **Experts** | Mandataire, then experts | Locard proposes the 3 best experts and explains each score. The mandataire solicits them; each expert gets an e-mail, accepts or refuses; the mandataire chooses among those who accepted. |
| 3 | **Contrat** | Mandataire | Signs the mandate (simple electronic signature) and generates the contract as a PDF with its SHA-256 fingerprint. |
| 4 | **Préparation** | Expert | Gets interview questions for the type of case, edits them as a checklist, exports a methodological guide (PDF). |
| 5 | **Analyse** | Expert | Adds witness statements (PV). Locard finds people, places, dates and amounts, then looks for contradictions between statements. It proposes hypotheses and a plan of forensic actions, and scores the technical reports. |
| 6 | **Rapport** | Expert generates, both read | Compiles everything into a versioned PDF report, with a chain-of-custody section and the fingerprints of every document. |

Throughout, **every algorithmic result has a "Pourquoi ?" button** that explains it in plain language: an expert's score, a detected inconsistency, a report's score.

### Modules

The specification splits the product into modules A to K. This is where each one lives.

| | Module | Role | Where |
|---|---|---|---|
| A | Mandate interface | Create and follow cases | `app/modules/cases`, `web/src/pages` |
| B | Expert matching | TF-IDF similarity + availability + experience, top 3 with justification | `app/modules/matching` |
| C | Contracts | LaTeX + Jinja2 to PDF, SHA-256, injection-safe | `app/modules/contracts` |
| D | Acceptance workflow | Pending, accepted, refused, chosen (state machine) | `app/modules/workflow` |
| E | Mission preparation | Questions, checklist, guide PDF | `app/modules/mission` |
| F | PV analysis | spaCy for people and places, rules for dates, amounts and contradictions, plus an optional language model that suggests more contradictions | `app/modules/pv` |
| G | Hypotheses and methodology | Hypotheses from the case and from the inconsistencies, ordered plan of actions | `app/modules/methodology` |
| H | Technical reports | Scores each report, builds the optimal resolution chain | `app/modules/reports/tech.py` |
| I | Final report | Versioned LaTeX PDF with chain of custody | `app/modules/reports/final.py` |
| J | Audit and security | Append-only log with a SHA-256 hash chain, integrity check, rotation | `app/modules/audit`, `app/modules/auth` |
| K | Explainability | `GET /xai/explain` for experts, inconsistencies and reports | `app/modules/xai` |

---

## Screenshots

| | |
|---|---|
| ![Sign in](docs/screenshots/01-connexion.png) **Sign in** | ![Dashboard](docs/screenshots/02-tableau-de-bord.png) **Dashboard** of the mandataire |
| ![Experts' answers](docs/screenshots/03-reponses-des-experts.png) **Experts' answers**: only an expert who accepted can be chosen | ![Contract](docs/screenshots/04-contrat.png) **Contract** with its SHA-256 and a "Vérifié" badge |
| ![Methodology](docs/screenshots/06-hypotheses-et-methodologie.png) **Hypotheses and plan** of forensic actions | ![Technical reports](docs/screenshots/07-rapports-techniques.png) **Technical reports** ranked, with the optimal chain |
| ![Final report](docs/screenshots/08-rapport-final.png) **Final report**: sections, PDF preview, fingerprint | ![Audit trail](docs/screenshots/09-journal-audit.png) **Audit trail** with the integrity check |
| ![Dark mode](docs/screenshots/10-mode-sombre.png) **Dark mode** | |

A style guide with the colours, typography and every reusable component is built into the app at `/style-guide`.

---

## How it works

```
 Browser ──► Caddy (HTTPS, serves the web app) ──► FastAPI ──► PostgreSQL (SQLite in development)
                                                      │
                                                      ├── spaCy  (fr_core_news_lg): people and places in PVs
                                                      ├── LaTeX  (pdflatex): contracts, guides, reports
                                                      ├── files  (PVs, PDFs, audit log)  in OUTPUT_DIR
                                                      └── SMTP   (Brevo): invitations and notices
```

- **Backend**: Python, FastAPI, SQLAlchemy 2, Pydantic. One service, modules as routers under `/api/v1`.
- **Frontend**: React 18, TypeScript, Material-UI v5 with a custom theme, Vite. French interface, light and dark mode.
- **Documents**: LaTeX templates filled by Jinja2. Everything a user types is escaped before it reaches LaTeX, `pdflatex` runs with `-no-shell-escape`, and a hostile text such as `\input{/etc/passwd}` is printed, never executed (there is a test for it).
- **Integrity**: a file's SHA-256 is computed when it is stored and checked again each time it is read. A PV, contract or report modified on disk is refused.
- **Accounts**: JWT access tokens (1 hour) and single-use refresh tokens (7 days), bcrypt passwords, lockout after 5 failed logins. Mandataires sign up themselves; **experts join through an e-mailed invitation link**.
- **Visibility**: a mandataire only sees their own cases, an investigator only the cases they were solicited for or chosen for. A case you cannot access answers *not found*, so identifiers cannot be probed.

### How the PV analysis works (module F)

spaCy's French model finds **people and places**. It has no date or amount labels, so **dates, times, amounts and events come from hand-written rules**. The contradictions are found by rules that compare the facts of all statements of a case:

- *temporal*: an action authorised after the date the account was said to be compromised; someone seen while declared absent;
- *geographic*: a trip that cannot be done in the stated time, or an on-site connection by someone declared on holiday elsewhere;
- *factual*: opposite states of the same object (door open and closed), an attachment opened before it was received.

These are **aids for the expert, not conclusions**. They only fire on explicit dates or weekdays, named people and known cities, and are deliberately cautious. Details and limits are in the module docstrings (`app/modules/pv/rules.py`).

#### Optional: contradictions suggested by a language model

The rules only recognise a few phrasings. On 14 planted contradictions between whole statements they found none, because the sentences were worded differently from any rule. So Locard can also ask a French natural language inference model ([DistilCamemBERT](https://huggingface.co/cmarkea/distilcamembert-base-nli), MIT licence, 272 MB) whether two sentences contradict each other.

- **How it runs.** The expert presses "Lancer l'analyse" under the statements. A background job picks sentence pairs that share words, scores them in both directions, and keeps at most 3 per pair of statements, only at a score of 0.95 or more. On a laptop CPU a case takes seconds. Results are stored and marked out of date if a PV is added later.
- **How it is shown.** As "Suggestion automatique" cards, **apart from the rule-based findings and outside the coherence score**. The model cannot tell a real contradiction from a pair that only looks contradictory (a different time, person or object), so every suggestion is for the expert to verify. Names can be masked like everywhere else, and each run is written to the audit log.
- **What it achieves.** On synthetic statements written for the experiment: 6 of 14 planted contradictions found and 2 false suggestions (about 43% recall and 75% precision), against 0 of 14 for the rules. These figures come from a small, hand-made set and are not an accuracy claim. The whole experiment, including a second model that was tested and left out, is in [`experiments/pv_nli/`](experiments/pv_nli/README.md).
- **It is optional.** Without `torch` and `transformers` (or with `LOCARD_ML=0`) the card does not appear and nothing else changes. See "First setup" for how to install it.

---

## Run it on your computer

### What you need

| | |
|---|---|
| Python | 3.11 or newer (developed and tested on 3.13) |
| Node.js | 22 |
| LaTeX | `pdflatex` on your PATH, with the packages `geometry`, `longtable`, `array`, `booktabs`, `lmodern`, `amssymb` (MiKTeX or TeX Live). Without it everything works except PDF generation. |
| Disk | about 1 GB for the French language model |

### First setup

```powershell
# from the project folder
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m spacy download fr_core_news_lg     # about 570 MB, once

cd web
npm install
cd ..
```

(On Linux or macOS the interpreter is `.venv/bin/python`.)

**Optional: the language model for contradiction suggestions** (about 1 GB of disk; the model itself downloads on first use):

```powershell
.\.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python -m pip install -r requirements-ml.txt
```

### Start

Two terminals, both from the project folder.

```powershell
# terminal 1: the API on port 8000
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000

# terminal 2: the web app on port 5173
cd web
npm run dev
```

Open **http://localhost:5173** (use `localhost`, not `127.0.0.1`). The API documentation (Swagger) is at http://localhost:8000/docs in development.

### Your first accounts

```powershell
# a mandataire (asks for a password of 12 characters or more)
.\.venv\Scripts\python -m app.cli create-user --email you@example.org --name "Your Name" --role mandataire
```

A development database comes with **60 demo experts** with fake addresses (`@experts.example`). To try the whole flow without sending real mail, log in as the mandataire, create a mandate, and solicit the experts. Their invitations are written as `.eml` files in `output/outbox/` (open one, the activation link is inside; the text is quoted-printable, so a mail client shows it properly). Open the link in a private window, choose a password, and you are that expert.

To make an expert account yourself without the invitation:

```powershell
.\.venv\Scripts\python -m app.cli list-experts --search dubois
.\.venv\Scripts\python -m app.cli create-user --email expert@example.org --name "Expert" --role investigateur --expert-id 12
```

### Real e-mails (Brevo)

Copy `.env.example` to `.env`, fill in your Brevo SMTP login, SMTP key and a verified sender, then check it:

```powershell
.\.venv\Scripts\python -m app.cli check-mail          # tests the login, sends nothing
.\.venv\Scripts\python -m app.cli send-test-mail --to you@example.org
```

`.env` is git-ignored: never commit it. Without `SMTP_HOST`, mail stays in the local outbox. Addresses on reserved domains (`.example`, `.test`, `example.com`) are **never** sent for real, so the demo experts can never cause bounces.

---

## Settings

Everything is read from environment variables, or from a `.env` file at the project root (a variable already set in your shell wins).

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./forensic.db` | Database. For PostgreSQL: `postgresql+psycopg://user:password@host:5432/dbname` |
| `OUTPUT_DIR` | `output` | Stored PVs, generated PDFs, the mail outbox |
| `AUDIT_LOG_PATH` | `logs/audit.jsonl` | Readable copy of the audit log |
| `AUDIT_LOG_MAX_MB` | `100` | Size at which the log file is archived as `.gz` |
| `LATEX_TIMEOUT` | `60` | Seconds allowed for one PDF |
| `JWT_SECRET` | random per start | Signing secret, 32 characters or more. **Required in production.** |
| `APP_BASE_URL` | `http://localhost:5173` | Address used in the links of e-mails |
| `SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASSWORD` `SMTP_FROM` | none | Mail relay. Without a host, mail goes to the outbox. |
| `SMTP_ALLOWED` | none | Optional: only these recipients (addresses or domains) get real mail |
| `RATE_LIMIT_PER_MIN` | `100` | Requests per minute per user (or per address when anonymous) |
| `LOGIN_LIMIT_PER_MIN` | `10` | Login, sign-up and activation attempts per minute per address |
| `TRUSTED_PROXIES` | none | Reverse proxies whose `X-Forwarded-For` is believed (needed behind Caddy or nginx) |
| `LOCARD_ENV` | development | Set to `production` to require `JWT_SECRET` and hide Swagger |
| `LOCARD_DOCS` | off in production | `1` shows Swagger in production |
| `LOCARD_SEED_DEMO` | `1` | `0` skips the fake demo experts (production) |
| `LOCARD_ML` | auto | `0` switches off the language-model suggestions even when the libraries are installed |
| `LOCARD_NLI_MODEL` | `cmarkea/distilcamembert-base-nli` | Hugging Face model id. `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` works too, but is 47 times slower for no better ranking on whole statements. |
| `LOCARD_NLI_MIN_SCORE` `LOCARD_NLI_CAP` | `0.95` `3` | Lowest score shown, and suggestions kept per pair of statements |
| `HF_HUB_OFFLINE` | none | `1` once the model is downloaded: never contact Hugging Face again |
| `BCRYPT_ROUNDS` | `12` | Password hashing cost |

`.env.example` (development) and `.env.production.example` (server) show the format.

---

## Administration commands

All run as `python -m app.cli <command>`.

| Command | What it does |
|---|---|
| `create-user` | Creates a mandataire or investigator account. Asks for the password on the terminal. |
| `list-experts` | Lists expert profiles (`--search` to filter). |
| `import-experts file.csv` | Loads real experts from a CSV (template in `docs/experts-template.csv`). Dry run unless `--apply`. |
| `remove-demo-experts` | Removes the fake demo experts that nothing refers to. Dry run unless `--apply`. |
| `check-mail` | Tests the SMTP login without sending. |
| `send-test-mail --to x` | Sends one test message. |
| `rotate-logs` | Archives the audit log file (it also rotates by itself at 100 MB). |
| `purge-expired` | RGPD: deletes interview data six months after the final report. Dry run unless `--apply`. |

---

## Tests

```powershell
.\.venv\Scripts\python -m pytest -q                       # the whole suite
.\.venv\Scripts\python -m pytest -q --cov=app             # with coverage
```

At the last full run: **165 tests passed, 90% of the code covered.** They cover accounts and access rules (including attack cases: forged, expired and `alg: none` tokens, reused refresh tokens, probing other users' cases), the invitation e-mails (against a fake authenticated mail server), the PV analysis (precision and recall on an annotated set), modules G, H and I, the PDF generation, the audit chain and its rotation, RGPD export and purge, rate limiting, the production start-up checks, and the language-model suggestions (with a stand-in model, plus two tests with the real model that are skipped when it is not installed).

The suite never sends real mail (it loads no `.env`) and uses its own temporary database. To run it on **PostgreSQL**, give it an empty database:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://user:password@127.0.0.1:5432/locard_test"
.\.venv\Scripts\python -m pytest -q
```

The whole suite passes on PostgreSQL 16 as well as on SQLite.

Front end checks:

```powershell
cd web
npx tsc --noEmit                                              # type check
npm run build                                                 # production build
node --experimental-strip-types scripts/check-contrast.mjs    # WCAG AA contrast of every colour pair, both modes
```

---

## Deploy it

Locard ships as three containers (PostgreSQL, the API, and Caddy serving the web app with automatic HTTPS). The full guide, step by step, is in **[docs/DEPLOY.md](docs/DEPLOY.md)**. In short:

```bash
git clone https://github.com/makeu05/forensic-assistant.git locard && cd locard
cp .env.production.example .env        # fill in the domain, secrets and Brevo settings
docker compose up -d --build
docker compose exec api python -m app.cli create-user --email you@example.org --name "You" --role mandataire
```

You need a Linux server with **4 GB of RAM** (the language model alone uses about 1 GB), Docker, a domain pointing at the server, and ports 80 and 443 open.

**Honest status of the deployment files.** The application itself was verified on PostgreSQL 16 and `requirements.txt` was verified in a clean environment. The Dockerfiles, the compose file and the Caddy configuration were **written but never built**, because Docker was not installed on the development machine. Expect to fix small things on the first build. The Dockerfile compiles a test document during the build, so a missing LaTeX package stops the build instead of failing later for a user.

Before going live, read the notes in the guide about backups (the database and the `locard-data` volume), e-mail deliverability (authenticate your domain in Brevo), and database updates (there is no migration tool yet).

---

## Security and data protection

What is in place:

- **Authentication**: JWT, single-use refresh tokens with theft detection, bcrypt, lockout, rate limiting (a stricter limit on login), security headers on every answer, no caching of API responses.
- **Access control**: roles and ownership enforced on the server for every route.
- **Chain of custody (ISO/IEC 27037)**: fingerprints on collection, verified on every read; an append-only audit log where each entry holds the hash of the previous one. The integrity check replays the whole chain and names the first broken entry. See **[docs/ISO27037.md](docs/ISO27037.md)**, which also lists what it does **not** guarantee.
- **RGPD**: a "Télécharger mes données" export, pseudonymisation of names ("Personne A", "Personne B") on screen and in reports, e-mails that never contain case details, and a six-month purge of interview data.
- **Files survive download managers**: tools such as Internet Download Manager swallow PDF downloads and hand the page an empty answer. The app therefore fetches PDFs as base64 inside JSON for previews and download buttons.

Not in place: encryption of files at rest, certified timestamps (RFC 3161), qualified electronic signatures, multi-factor authentication, and automatic backups.

---

## Project layout

```
app/
  main.py                 the API: mounts every module under /api/v1
  cli.py                  administration commands
  db.py                   database engine and sessions
  core/                   config (.env), mail, security (rate limit, headers), files, LaTeX
  modules/
    auth/                 accounts, JWT, invitations, access rules
    cases/  matching/  workflow/  contracts/  mission/   modules A to E
    pv/  methodology/  reports/                          modules F (rules and model), G, H, I
    audit/  xai/  privacy/                               modules J, K, and RGPD
  templates/              LaTeX templates (contract, guide, report)
web/
  src/theme/              colour tokens and the MUI theme
  src/components/ui/      reusable components (ScoreRing, HashBadge, EntityHighlighter ...)
  src/pages/              screens; src/pages/case/ holds the six steps
  scripts/                contrast checker
experiments/pv_nli/       the experiment behind the language-model suggestions (data, scripts, results, decision)
tests/                    pytest suite and the annotated PV dataset
docs/                     deployment guide, ISO 27037, expert CSV template, screenshots
deploy/                   Caddyfile and the LaTeX package check
Dockerfile.api  Dockerfile.web  docker-compose.yml     requirements.txt  requirements-ml.txt (optional)
```

The API has 45 endpoints, grouped under `/api/v1/` as `auth`, `cases`, `matching`, `solicitations`, `contracts`, `mission`, `pv`, `semantic`, `methodology`, `reports`, `audit`, `xai`, `privacy` and `health`. Swagger lists them all in development.

---

## What Locard does not do

Being clear about this matters more than a long feature list.

- **It does not decide.** Inconsistencies and hypotheses are produced by rules. The expert reads, verifies and signs the conclusion.
- **The PV analysis is mostly rule-based.** The rules need explicit dates or weekdays and named people, and their accuracy was measured on a small set of statements written together with them (a regression check, not a real accuracy figure). The only machine learning is the optional model that suggests contradictions: it misses more than half of them, is wrong about one suggestion in four, and was measured on synthetic data. A fair evaluation of either needs statements nobody tuned anything on.
- **Expert matching is keyword similarity** (TF-IDF), not a judgement of skill. It is an aid for the mandataire's choice.
- **No acquisition of physical evidence** (disk images, memory). Out of scope.
- **The audit log is tamper-evident, not tamper-proof.** Someone who controls the database and recomputes the whole chain would produce a consistent log. The remedy is an external timestamp, which is not implemented.
- **The mandate signature is a simple electronic signature**, not a qualified one.
- **Only PV text** (`.txt` or pasted). No Word or PDF import, no OCR.
- **No password reset** yet, and no admin screen: accounts and experts are managed with the commands above.
- **No migration tool.** Tables are created at first start; a future version that adds a column will need a migration. Back up before updating.
- **The rate limiter keeps its counters in memory**, per API process.
- **The Docker deployment has not been run** (see above).

---

## More documentation

| | |
|---|---|
| [docs/DEPLOY.md](docs/DEPLOY.md) | Deploying with Docker Compose, backups, updates |
| [docs/ISO27037.md](docs/ISO27037.md) | Chain of custody, what is guaranteed and what is not (in French) |
| [docs/experts-template.csv](docs/experts-template.csv) | Template for importing real experts |
| [HANDOFF.md](HANDOFF.md) | Working notes for whoever continues the project |

## Credits

Built as the integrating project of the 4th-year cybersecurity engineering class supervised by Prof. Thierry Minka, following the specification "Assistant intelligent semi-autonome d'investigation numerique" (v2.0).

No licence has been chosen yet: until one is added, all rights are reserved by default.
