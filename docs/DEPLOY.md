# Deploying Locard

Locard runs as three containers: **PostgreSQL**, the **API** (FastAPI, spaCy, LaTeX) and the **web** server
(Caddy: serves the app, forwards `/api`, and gets the HTTPS certificate by itself).

> **Status of these files.** The application was tested on PostgreSQL 16 (the full test suite passes on it),
> and `requirements.txt` was verified in a clean environment. The Dockerfiles and the compose file were
> **not built or run** by their author, because Docker was not installed on the development machine. Expect
> to fix small things on the first build, and tell me what the error says.

## What you need

| | |
|---|---|
| A server | Linux, **4 GB RAM** (the French language model alone needs about 1 GB), 2 vCPU, 20 GB disk. 2 GB is too small. |
| Docker | Docker Engine with the compose plugin (`docker compose version`). |
| A domain | `belva.work.gd` is fine. Create an **A record** pointing to the server's IP address in the panel where you manage that domain. Ports **80 and 443** must be open to the internet (Caddy needs both to obtain the certificate). |
| An e-mail relay | Your Brevo account (already working). |

## 1. Get the code on the server

```bash
git clone https://github.com/makeu05/forensic-assistant.git locard
cd locard
```

## 2. Create the settings file

```bash
cp .env.production.example .env
nano .env
```

Fill in:

- `DOMAIN` and `APP_BASE_URL` (the public address; `https://` in `APP_BASE_URL`),
- `POSTGRES_PASSWORD` and `JWT_SECRET`: generate each with `openssl rand -hex 32`,
- the `SMTP_*` values from your local `.env` (login, SMTP key, sender).

`.env` stays on the server. It is git-ignored; do not copy it anywhere else.

To try the stack **before you have a domain**, set `DOMAIN=:80` and `APP_BASE_URL=http://<server-ip>`. That runs over
plain HTTP, which is only acceptable for a short test: passwords would travel unencrypted.

## 3. Start

```bash
docker compose up -d --build
docker compose ps            # all three should be "running" (api becomes "healthy" after about a minute)
docker compose logs -f api   # watch it start; Ctrl+C leaves the logs, not the app
```

The first build downloads and compiles a lot (LaTeX, the language model, the web app): expect 10 to 15 minutes.

Then open `https://belva.work.gd`. The certificate is requested on the first visit and can take a few seconds.

## 4. First accounts and real experts

The live database is empty: no demo experts, no users.

```bash
# your own mandataire account (asks for the password; 12 characters minimum)
docker compose exec api python -m app.cli create-user --email you@example.org --name "Your Name" --role mandataire

# the real experts: fill docs/experts-template.csv, then
docker compose cp experts.csv api:/tmp/experts.csv
docker compose exec api python -m app.cli import-experts /tmp/experts.csv            # dry run first
docker compose exec api python -m app.cli import-experts /tmp/experts.csv --apply
```

Experts do not get passwords from you: when a mandataire solicits one, Locard e-mails an invitation link.
Matching needs **at least three** experts in the base to propose three.

Check that mail works from the server:

```bash
docker compose exec api python -m app.cli check-mail
docker compose exec api python -m app.cli send-test-mail --to you@example.org
```

## 5. E-mail deliverability (do this once)

In Brevo, open *Senders, domains & dedicated IPs, then Domains*, add your domain and publish the DNS records it
shows (DKIM, SPF/DMARC). Without them, Gmail may spam-folder the invitations. A free subdomain provider might
not let you add every record type: if it refuses, a cheap own domain solves it.

## Running it

| Task | Command |
|---|---|
| Update to the latest code | `git pull && docker compose up -d --build` |
| Logs | `docker compose logs -f api` |
| Stop / start | `docker compose stop` / `docker compose start` |
| Delete interview data older than 6 months (RGPD) | `docker compose exec api python -m app.cli purge-expired` (dry run; add `--apply`) |
| Rotate the audit log file | automatic at 100 MB; or `docker compose exec api python -m app.cli rotate-logs` |

Put the purge on a monthly schedule with cron once you have decided to use it.

### Backups: do not skip this

Two things hold your data. Back up both, and **copy the backups off the server**.

```bash
# the database
docker compose exec -T db pg_dump -U locard locard | gzip > locard-db-$(date +%F).sql.gz

# the files: generated PDFs, stored PVs, audit log file
docker run --rm -v locard_locard-data:/data -v "$PWD":/backup alpine tar czf /backup/locard-files-$(date +%F).tgz -C /data .
```

A backup you have never restored is a hope, not a backup: try restoring once on a spare machine.

## Optional: the language model for contradiction suggestions

Locard can suggest contradictions between witness statements with a small language model (see the README, module F).
It is off by default in the image, which stays small. To include it:

1. Set `LOCARD_ML_BUILD=1` in `.env` (see `.env.production.example`).
2. Rebuild: `docker compose up -d --build`. This adds about 1 GB (CPU build of PyTorch and the 272 MB model) and a few
   minutes. The model is downloaded **during the build**, so the running server never contacts Hugging Face.
3. Check it: the "Suggestions du modèle" card appears under the statements of a case with two or more PVs.

Keep an eye on memory: the model needs about 1 GB of RAM once loaded, on top of spaCy. A 2 GB server is tight; 4 GB is comfortable.
If the card does not appear, `docker compose exec api python -c "from app.modules.pv import semantic; print(semantic.availability())"`
says why. This path, like the rest of the Docker files, has not been built yet.

## Things to know

- **Database changes.** The tables are created when the API first starts. A later version that adds a column
  needs a migration; Alembic is not set up yet. Until it is, take a backup before each update.
- **Sessions** survive restarts only because `JWT_SECRET` is fixed in `.env`.
- **Swagger** (`/docs`) is off in production. Set `LOCARD_DOCS=1` in `.env` to enable it temporarily.
- **Rate limiting** counts per API process and uses the real client address through Caddy. If you put another
  proxy (for example Cloudflare) in front of Caddy, add its address range to `TRUSTED_PROXIES`.
- **Not provided:** automatic backups, monitoring, encryption of files at rest, and a staging environment.
- **Security is shared:** keep the server updated, allow SSH by key only, and open only ports 22, 80 and 443.
