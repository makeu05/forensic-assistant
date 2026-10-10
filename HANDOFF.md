# Locard: project handoff (assistant intelligent d'investigation numerique)

Context file for continuing this project in a new chat. Written 2026-10-07.
Owner git identity for this repo: MAKEU05 <makeustelybelva@gmail.com> (personal project, NOT the NexCQI work account). Set locally in `.git/config`. Never add a Co-Authored-By line.

## 1. What the project is

Capstone ("Projet integrateur") for a 4th-year cybersecurity engineering class (Prof. Thierry MINKA, spec v2.0 dated 24 Oct 2025). Goal: a semi-autonomous digital forensics assistant that supports a mandataire (judge, company head, individual) and an investigator through: mandate creation, expert selection, mission preparation, evidence analysis, final expert report. Must respect chain of custody (ISO/IEC 27037:2012), GDPR (RGPD) and keep full traceability.

Original team plan: 27 students, 9 teams of 3, one module each (A to I) plus an integration team (API Gateway, J, K). Here, the work is being built end to end by one person with Claude.

Spec hard requirements worth remembering:
- Stack imposed: Python 3.11+, FastAPI, PostgreSQL 15+, SQLAlchemy 2.0 + Alembic, React 18 + TypeScript + MUI (or Ant Design), spaCy 3.7 with `fr_core_news_lg`, scikit-learn TF-IDF, LaTeX + Jinja2 + pdflatex, SHA-256, JWT, Docker Compose, GitHub Actions.
- Quality targets: tests coverage >= 70% per module, API < 2 s (p95), 100% of actions logged, OpenAPI 3.0 docs.
- 11 modules A to K behind one API Gateway under `/api/v1`.

### Module list (spec)
| Module | Role | Priority |
|---|---|---|
| A | Mandataire interface (create mandate, see 3 experts, download signed mandate PDF, status dashboard) | MVP |
| B | Expert matching (TF-IDF, 50-100 expert profiles, score 60% text / 20% availability / 20% experience, top 3 with justification) | MVP |
| C | Contract/mandate PDF generator (LaTeX + Jinja2, SHA-256 of PDF) | MVP |
| D | Expert acceptance workflow (pending, accepted, refused, chosen) | MVP |
| E | Mission preparation (questions per case type, witness list, checklist, guide PDF) | MVP |
| F | PV (interview report) ingestion + analysis: spaCy NER (persons, places, dates, amounts), detect temporal / geographic / factual inconsistencies | MVP (minimal) |
| G | Hypotheses + forensic methodology plan from inconsistencies | Stretch |
| H | Technical reports scoring and optimal resolution chain | Stretch |
| I | Final expert report PDF (LaTeX, 5+ sections) | MVP (minimal) |
| J | Security + immutable audit logs, hashing, integrity verification | MVP |
| K | Explainability (XAI) | Stretch |

Test dataset in spec (Annex B): fraud (witness 1 authorizes transfer 10/10/2025, witness 2 says account compromised 05/10/2025 -> temporal inconsistency), network intrusion (SSH 03:42, employee on vacation in Paris -> geographic), malware (clicked attachment Tuesday, email received Wednesday per logs -> factual).

## 2. Environment facts

- Windows 11, PowerShell + Git Bash. Python 3.13.2, Node 22.14, MiKTeX pdflatex available. **Docker is NOT installed** (so no Docker Compose run yet).
- Project path: `C:\Users\belva\Desktop\forensic-assistant` (deliberately outside the NexCQI work repos).
- Python venv: `.venv` inside the project. Run tests with `./.venv/Scripts/python -m pytest -q`.
- DB: SQLAlchemy, `DATABASE_URL` env var, default `sqlite:///./forensic.db`. PostgreSQL is supported by code but has NOT been run.
- Env vars: `DATABASE_URL`, `AUDIT_LOG_PATH` (default `logs/audit.jsonl`), `OUTPUT_DIR` (default `output`), `LATEX_TIMEOUT` (default 60 s).

## 3. What has been built (backend, all tested)

Layout:
```
app/
  main.py                 gateway: mounts all routers under /api/v1, creates tables, seeds experts
  db.py                   engine, SessionLocal, Base, get_db
  core/latex.py           Jinja2 (custom delimiters << >> and <% %>) + `tex` escape filter + pdflatex runner
  templates/mandat.tex.j2, guide.tex.j2
  modules/
    audit/      (J)  service.py, router.py
    cases/      (A)  router.py   (Case + MandateSignature models)
    matching/   (B)  service.py, seed.py, router.py
    workflow/   (D)  router.py
    contracts/  (C)  router.py
    mission/    (E)  router.py
tests/            conftest.py, test_foundation.py, test_workflow_pdf.py
web/              React front end (see section 4)
```

Implemented behavior:
- **J audit**: every action is a row in `audit_log` and a line in a JSONL file. Each entry stores `prev_hash` and `entry_hash` (SHA-256 chain), so editing any past row is detected by `GET /audit/chain/verify`. Files are SHA-256 hashed when a `file_path` is logged. Endpoints: `POST /audit/log`, `POST /audit/verify` (200 valid / 400 mismatch), `GET /audit/logs?case_id=`, `GET /audit/chain/verify`. Other modules call `log_action()` in process.
- **A cases**: `POST /cases` (validated: case_type in fraude_bancaire / intrusion_reseau / malware, priority basse/moyenne/haute, description >= 10 chars), `GET /cases` (list, max 50, includes `signed`), `GET /cases/{id}` (includes `signed`), `GET /cases/{id}/experts` (runs matching), `POST /cases/{id}/sign` (simple e-signature: name + timestamp, stored in `mandate_signatures`, idempotent, logged).
- **B matching**: 60 deterministic seeded experts. TF-IDF cosine similarity. Fix vs the spec: competence tags use underscores (`forensic_bancaire`), so text is normalized (`_` to space) otherwise nothing would match. Returns top 3 with `score`, `breakdown`, `justification`. `POST /matching/experts` also exists.
- **D workflow**: state machine pending -> accepted | refused, accepted -> chosen. Invalid transitions return 409 (cannot answer twice, cannot choose refused or pending, cannot choose twice per case). Endpoints: `POST /solicitations`, `GET /solicitations?case_id=` (includes `expert_nom`), `PUT /solicitations/{id}/respond`, `POST /solicitations/select` (sets case `chosen_expert_id`, status `en_cours`).
- **C contracts**: `POST /contracts/generate {case_id}` requires a chosen expert (409) AND a signed mandate (409). Renders LaTeX with escaping (tested with a hostile description containing `\input{/etc/passwd}`), compiles with `-no-shell-escape`, stores SHA-256. `GET /contracts?case_id=` returns latest contract, `GET /contracts/{id}/download` re-verifies the hash before serving (409 if the file was altered).
- **E mission**: `POST /mission/prepare {case_id}` returns questions (5 per case type), empty witness list, checklist, and a guide PDF; `GET /mission/{case_id}/guide.pdf`.
- LaTeX compile errors now report the first `!` line of the log. `guide.tex.j2` needs `amssymb` (for `\square`).

Tests: **14 passed** at last run (`pytest -q`), covering the full A -> B -> D -> sign -> C flow, audit chain tamper detection, state machine, LaTeX escaping, PDF generation, mission guide.

### Module F (PV analysis), added 2026-10-07
- Files: `app/modules/pv/` (`nlp.py` extraction, `rules.py` inconsistency rules, `router.py` API + `pvs` table). spaCy `fr_core_news_lg` is installed in the venv (about 570 MB) and loaded once at startup.
- spaCy gives persons and places only (the French model has no DATE/MONEY labels). Dates (numeric, textual, ISO, ranges, "depuis le"), times, amounts, weekdays, titled persons ("M. Dupont" fallback) and event facts come from rules on an accent-folded copy of the text.
- Endpoints: `POST /pv/analyze` (stores PV file under `output/pv/<case>/`, SHA-256 on receipt, upsert by `pv_id`, logs to J, optional `pseudonymize` flag), `GET /pv?case_id=`, `GET /pv/report?case_id=&pseudonymize=`.
- Rules compare facts across all PVs of a case: temporelle (action after compromise, sighting during declared absence), geographique (impossible trip by distance/speed table, on-site presence during declared absence abroad), factuelle (opposite states of the same object, attachment opened before it was received).
- Measured on `tests/data/pv_dataset.json` (10 hand-annotated synthetic PVs, written together with the rules, so treat as a regression check, not a real accuracy claim): NER precision 1.00, recall 1.00 (46 items); every case yields exactly the expected inconsistency type; clean PV yields none; 5000-word PV analysed under 3 s. 28 tests pass, total coverage 94%.
- Known limits: rules cover patterns, not free reasoning (needs explicit dates or weekdays, named persons, known cities); person matching is by surname; the spec's geographic example (IP + vacation) only fires when the same named person appears in both PVs.
- Fixed a test-isolation bug: `test_chain_detects_tampering` forged audit entry 1 in the shared session DB and never restored it.

## 4. Module A front end (written, builds, NOT yet verified in a browser)

`web/` (Vite + React 18 + TypeScript + MUI + axios). Dev proxy: `/api` -> `http://127.0.0.1:8000`, dev port 5173.
- `src/api.ts` typed API client + French labels + `errorMessage()` for FastAPI errors.
- `src/App.tsx` simple state router: dashboard / new / case.
- `src/components/Dashboard.tsx` case table with status chips and signed flag.
- `src/components/CaseForm.tsx` creation form with client-side validation mirroring the backend.
- `src/components/CaseDetail.tsx` stepper: Experts proposes -> Reponses et selection -> Signature -> Mandat PDF. Accept/Refuse buttons simulate the expert response (the real expert UI belongs to module D, not built). Shows SHA-256 and a download button.
- `npm run build` (tsc + vite build) **succeeds**.

## 5. Current blockers (where we stopped)

1. **Port 8000 already in use.** Starting `uvicorn app.main:app --port 8000` failed with WinError 10048. A leftover uvicorn from an earlier session is probably still running with OLD code (no `/sign`, no `GET /cases`). I was about to identify the owning process (PowerShell `Get-NetTCPConnection -LocalPort 8000`) and confirm it is our own earlier server before stopping it. Do not kill an unrelated process.
2. **`npm run dev` crashes** with `Missing export internal_processStyles from '@mui/styled-engine'`. Cause: `npm install @mui/material@5` resolved to MUI **9.4.0** (see `web/package.json`), and the dev pre-bundler hits a version mismatch (the production build passes). Planned fix: pin `@mui/material` and `@mui/icons-material` to `^6` (or `^5`), keep `@emotion/react` and `@emotion/styled`, reinstall, rebuild. Also keep `typescript@5` (the latest TypeScript release shipped a native binary that was missing on Windows).
3. Because of 1 and 2, the full flow has NOT yet been exercised through the browser or the Vite proxy. The backend flow is verified by pytest only.

## 6. Git state

Repo: `C:\Users\belva\Desktop\forensic-assistant`, branch default, author MAKEU05.
- Commit 1: gateway, audit (J), cases (A), matching (B).
- Commit 2: workflow (D), contracts (C), mission (E), shared LaTeX helper.
- **Uncommitted:** backend additions for Module A (list cases, signature, contract-by-case, contract gating on signature, expert name in solicitations, updated tests) and the whole `web/` folder. `.gitignore` already excludes `.venv`, `*.db`, `logs/`, `output/`, `node_modules/`. Consider adding `web/dist/`.
- No remote exists. Nothing has been pushed. A GitHub repo under the MAKEU05 account has not been created.

## 7. Next steps (suggested order)

1. Free port 8000 safely, restart API; fix MUI version; start `npm run dev`; click through the whole flow at http://127.0.0.1:5173 (create mandate, solicit, accept, choose, sign, generate, download PDF). Fix anything found.
2. Run `pytest`, commit Module A (backend + web) as MAKEU05.
3. DONE (see Module F above, backend only; PV upload screen still to build). Original note: install spaCy and `fr_core_news_lg` (about 570 MB, venv only; ask the user first). Implement NER (persons, places, dates, amounts) and the three inconsistency types, using the spec dataset above. The spec's sample code is a stub (`dates_parsed = [datetime.now()]  # Simulation`), so real date parsing and cross-PV comparison must be written. Target: NER precision >= 80%, recall >= 75%, < 3 s for a 5000-word PV, false positives < 30%.
4. **Module I**: final report PDF compiled from F (and G/H when present), 5+ sections, includes chain-of-custody section and RGPD mention, plus hash logged in J.
5. Wire audit logging for F and I; add a PV upload screen to the front end and a "final report" step.
6. Dockerfiles + `docker-compose.yml` (PostgreSQL, API, web). Cannot be tested locally until Docker is installed. Add Alembic migrations (currently `create_all`; changing existing columns in `forensic.db` would need a migration or a fresh DB).
7. GitHub Actions CI (pytest, black, flake8, mypy), coverage report >= 70%.
8. Stretch: G, H, K, JWT auth on the gateway, rate limiting, pseudonymization flag.
9. Update the CV from real results (see below).

## 8. CV entry (to finalize at the end, using real numbers only)

Draft, to be completed with measured results (test count, coverage %, latency, NER precision and recall):

**Intelligent Semi-Autonomous Digital Forensics Assistant** | Capstone project, 4th-year Cybersecurity Engineering | Oct 2025 to present
- Designed and built an end-to-end investigation platform (mandate, expert matching, acceptance workflow, signed mandate PDF, mission preparation, audit trail) as a modular FastAPI backend with a React/TypeScript front end.
- Implemented a tamper-evident audit log (SHA-256 hash chain, JSONL + database) aligned with ISO/IEC 27037 chain of custody; integrity verification detects any altered entry.
- Built TF-IDF expert matching with explainable multicriteria scoring, and a LaTeX/Jinja2 PDF pipeline hardened against LaTeX injection (escaping, no shell-escape, hash verification on download).
- Stack: Python, FastAPI, SQLAlchemy, PostgreSQL/SQLite, scikit-learn, spaCy, LaTeX, React, TypeScript, MUI, pytest, Docker.

Rules from the user's organization brand guideline that apply to any document produced (CV included if branded): no em dashes anywhere (use colons, parentheses or hyphens), Montserrat typeface, navy #14377B / blue #2E86C8 / sky #38A1E8 / light #F7F7FB palette.

## 9. Working agreements with the user

- Personal project: use the MAKEU05 identity only. Do not touch the NexCQI work repos or the `sbtenku-png` identity.
- Ask before risky or outward-facing actions (killing processes, pushing, creating remote repos, large downloads, deleting files). Never delete files.
- Do not paste real personal data, credentials or secrets into prompts or files. All data here is synthetic.
- Answer in the user's language style (English with French domain terms is fine). Keep UI text in French.


## 10. Update 2026-10-07 (second session): auth, mail, G/H/I, redesign

State at the end of this session: 76 backend tests, 91% coverage, web build clean, end-to-end browser run passes.

- **Name**: the app is called **Locard**.
- **Auth**: JWT (access 1 h, refresh 7 d, rotation with reuse detection), bcrypt, 2 roles (`mandataire`, `investigateur`), lockout after 5 failures, every route except `/health` and `/auth/*` needs a token. A mandataire sees only their cases (`cases.owner_id`), an investigator only cases where their expert profile is solicited or chosen; inaccessible cases answer 404. Audit entries carry the real user. `JWT_SECRET` env var (32+ chars); if unset a random one is used and sessions end on restart.
- **Expert accounts**: created from an invitation e-mail (single-use link, 7 days, token stored hashed) sent when a mandataire solicits an expert with no account. Admin CLI: `python -m app.cli create-user | list-experts | send-test-mail`.
- **Mail**: `app/core/mail.py`. Without `SMTP_HOST` mail is only written to `OUTPUT_DIR/outbox/*.eml` (quoted-printable, decode before reading). Real sending needs SMTP_HOST/PORT/USER/PASSWORD/FROM typed by the user in their own shell. Outbound port 25 is blocked on this machine, so direct delivery to Gmail is not possible; Gmail SMTP on 587 works with an app password. Nothing has been sent to a real address.
- **New modules**: G `GET /methodology`, H `POST /reports/analyze` + `GET /reports/analysis`, I `POST /reports/generate` (LaTeX, versions, SHA-256), PV detail with highlight segments, audit filters, case lifecycle (`stages`, `progress`, `last_activity`, solicitation counts).
- **Front end**: full redesign from the user's brief (MUI v5, tokens in `web/src/theme`, 9 components in `web/src/components/ui`, screens in `web/src/pages`, style guide at `/style-guide`). Old components moved (not deleted) to `web/legacy/`. `vite.config.ts` aliases `@mui/icons-material/*` to the ES build (without it the page is blank with MUI 5 + this Vite). `API_TARGET`/`WEB_PORT` env vars allow a second instance.
- **Checks**: `node --experimental-strip-types web/scripts/check-contrast.mjs` (WCAG AA over all token pairs, both modes). Brief colours that failed AA as text got text variants (documented in `tokens.ts`). Browser e2e used puppeteer-core + axe-core in a scratch folder (not in the repo).
- **Dev accounts** were created on `forensic.db`: mandataire@locard.test and alice.dubois0@experts.example (passwords were shown once in chat, not stored anywhere).
- **Known gaps**: bundle is one 746 kB chunk (route code-splitting not done); PV upload accepts .txt only; no password reset; no Docker/CI yet; `tooltip` popups trigger an axe "region" notice (portal, known false positive); expert suggestions for witnesses are empty (MVP).

## 11. Update 2026-10-10: deployment prep, mail, README

- **Verified**: whole suite (143 tests, 89% coverage) passes on SQLite and on PostgreSQL 16.8 (`TEST_DATABASE_URL`). `requirements.txt` was incomplete (PyJWT, bcrypt, psycopg were missing) and is now verified in a clean venv.
- **Deployment files** (`Dockerfile.api`, `Dockerfile.web`, `docker-compose.yml`, `deploy/Caddyfile`, `docs/DEPLOY.md`) are written but **never built**: Docker is not installed on this machine. Target domain: belva.work.gd. Host not chosen yet.
- **Production switches**: `LOCARD_ENV=production` requires `JWT_SECRET` and hides Swagger; `LOCARD_SEED_DEMO=0` skips the fake experts; `TRUSTED_PROXIES` lets the rate limiter see real client addresses behind Caddy (without it everyone shares one bucket). Real experts: `import-experts` CSV, `remove-demo-experts`.
- **Mail**: Brevo works (login verified, test mail reached an inbox, not spam). Settings live in the git-ignored `.env`. Reserved domains (`.example`, `.test`) are never sent for real. In the dev database two experts carry real addresses for workflow testing (ids 9 and 17); experts.example addresses are held in `output/outbox`.
- **Download managers**: Internet Download Manager (installed on this machine) swallows PDF downloads and returns an empty 204, which broke the PDF preview and "Télécharger". All PDF endpoints now accept `?encoding=base64` (JSON); the web app uses it. Raw downloads (curl) still work. The data export no longer sends `Content-Disposition`.
- **Also added since section 10**: rate limiting + security headers, audit log rotation (gzip + hashed marker), RGPD export and `purge-expired`, Module K `GET /xai/explain`, `docs/ISO27037.md`.
- **README.md** written, with 10 screenshots in `docs/screenshots` (taken from a real end-to-end run with puppeteer in a scratch folder, not part of the repo).
- **Still open**: CI (GitHub Actions) and lint (flake8 reported 12 small issues), Cypress tests, Alembic migrations, first real Docker build, Brevo domain authentication (DKIM/SPF) for belva.work.gd, code splitting of the 746 kB bundle.
