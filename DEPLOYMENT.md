# Deploying Lexa

Lexa is production-structured: migrations, security headers, a gunicorn entrypoint, and
deploy manifests are included. This guide covers the steps to go live.

## What's in the box

- `Dockerfile` + `docker-compose.yml` — container deploy (app + Postgres).
- `Procfile` — Heroku / Railway.
- `render.yaml` — Render blueprint (web service + Postgres + health check).
- `start.sh` — production entrypoint: runs `alembic upgrade head`, then gunicorn + uvicorn workers.
- `.github/workflows/ci.yml` — runs the test suite + migrations on every push/PR.

## Required production environment

Set these (never commit real secrets — `.env` is git-ignored):

```
JWT_SECRET=<long random string>
DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/lexa
AUTO_CREATE_TABLES=false          # schema is owned by Alembic in prod
SECURITY_HEADERS_ENABLED=true
FORCE_HTTPS=true                  # send HSTS + redirect when behind TLS
CORS_ORIGINS=https://your-domain  # NOT "*" in production
```

To enable real reasoning and live data:

```
LLM_PROVIDER=live
ANTHROPIC_API_KEY=...             # and/or OPENAI_API_KEY / GOOGLE_API_KEY
EMBEDDINGS_BACKEND=sentence_transformers   # pip install sentence-transformers
LIVE_SOURCES_ENABLED=true
LIVE_SOURCES=federal_register,courtlistener
```

Also set current model ids in `app/config.py` `MODEL_REGISTRY` (the shipped ids are placeholders).

## Option A — Render (one click-ish)

1. Push the repo to GitHub.
2. In Render: New → Blueprint → pick this repo. `render.yaml` provisions a web service + Postgres,
   generates `JWT_SECRET`, and runs migrations via `start.sh`.
3. Set `CORS_ORIGINS` and any provider keys in the dashboard. Deploy.

## Option B — Docker / any container host

```bash
docker compose up --build        # local: app on :8000, Postgres on :5432
# or build and run just the app against managed Postgres:
docker build -t lexa .
docker run -p 8000:8000 --env-file .env lexa
```

The container runs `uvicorn` by default; for the migrate-then-gunicorn flow use `bash start.sh`
as the command (compose/Procfile/render already do).

## Option C — Heroku / Railway

The `Procfile` runs migrations as a `release` step and serves with gunicorn. Provision a
Postgres add-on, set the env vars above, and deploy.

## Pre-launch checklist (still on you)

- [ ] Real model API key(s) set; `MODEL_REGISTRY` ids updated to current models.
- [ ] A real, licensed/lawful legal corpus ingested (the bundled corpus is small);
      run `scripts/ingest_courtlistener.py` and/or enable live sources.
- [ ] Switch billing from the dev stub to Stripe (Checkout + webhook).
- [ ] `EMBEDDINGS_BACKEND=sentence_transformers` (or a provider) for quality retrieval.
- [ ] Move the in-memory rate limiter to Redis if running multiple workers/instances.
- [ ] Legal/compliance review of disclaimers, data handling, and unauthorized-practice
      boundaries for your jurisdictions.
- [ ] Put a real secret manager in front of env vars; rotate `JWT_SECRET`.

## Push to a new GitHub repo

The folder is already a git repo, but `origin` points at an unrelated project
(`Idea-Validater`). Point it at a fresh repo and push, from your machine where your GitHub
login works.

**1. Create an empty repo** named e.g. `lexa` on GitHub (no README/.gitignore so it doesn't
conflict) — or use the GitHub CLI in step 2.

**2a. Web-created repo** — repoint origin and push:

```bash
cd "C:\Users\Mrinall Samal\Claude\Projects\legal ai"
git remote remove origin
git remote add origin https://github.com/MrinallSamal-byte/lexa.git
git add -A
git commit -m "Production-ready: hardening, live gov sources, deploy manifests, UI"
git branch -M main
git push -u origin main
```

**2b. Or with the GitHub CLI** (creates the repo and pushes in one go):

```bash
cd "C:\Users\Mrinall Samal\Claude\Projects\legal ai"
git add -A
git commit -m "Production-ready: hardening, live gov sources, deploy manifests, UI"
gh repo create lexa --private --source . --remote origin --push
```

> `.env`, `*.db`, the vector store, and caches are git-ignored, so no secrets or local data
> get committed. Double-check with `git status` before pushing.

