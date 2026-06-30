<div align="center">

# Lexa — Grounded Legal AI

**Legal research you can verify.** Lexa retrieves real source text, drafts an answer that
cites it, and an independent agent checks every claim before you see it — and says "I don't
know" instead of inventing law.

</div>

> **Not legal advice.** Lexa provides general legal information, grounded in sources, and is
> not a substitute for a licensed attorney. Always confirm important matters with counsel in
> your jurisdiction.

---

## Table of contents

- [Why Lexa](#why-lexa)
- [How it works](#how-it-works)
- [Where the data comes from](#where-the-data-comes-from)
- [Quick start](#quick-start)
- [Turning on real reasoning & live data](#turning-on-real-reasoning--live-data)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Project layout](#project-layout)
- [Testing](#testing)
- [Database migrations](#database-migrations)
- [Deployment](#deployment)
- [Security & privacy](#security--privacy)
- [Honest limitations](#honest-limitations)
- [Roadmap](#roadmap)

---

## Why Lexa

Most "legal AI" will confidently answer anything — including inventing case names, statute
sections, and citations that don't exist. Lexa is built the opposite way:

- **Grounded** — answers are written *only* from retrieved source passages.
- **Cited** — every legal statement carries an inline citation you can open and read.
- **Verified** — a separate agent checks each claim against its source and flags or removes
  anything it can't confirm.
- **Honest** — when the sources don't support an answer, Lexa abstains instead of guessing.

It runs offline out of the box (mock model + local embedder), so you can exercise the entire
flow with no API keys, then plug in real models and live government data.

## How it works

A three-agent pipeline makes each step narrow and independently checkable:

```
        ┌────────────┐     ┌──────────┐     ┌───────────┐
 Q ───▶ │ Researcher │ ──▶ │ Retrieve │ ──▶ │  Drafter  │ ──┐
        │  (issue +  │     │  grounded│     │ cites each│   │
        │  queries)  │     │  facts   │     │  claim    │   │
        └────────────┘     └────┬─────┘     └───────────┘   │
                                │ + optional LIVE gov data  │
                                ▼                           ▼
                          ┌───────────┐             ┌───────────────┐
                          │  abstain  │◀── no ───── │ enough grounded│
                          │ "I don't  │   grounding │    support?     │
                          │  know"    │             └──────┬─────────┘
                          └───────────┘                    │ yes
                                                           ▼
                                                  ┌──────────────────┐
                                                  │     Verifier     │
                                                  │ checks every claim│
                                                  │ approve/revise/  │
                                                  │ reject (+ repair)│
                                                  └────────┬─────────┘
                                                           ▼
                                              cited, verified answer (streamed)
```

1. **Researcher** spots the legal issue and generates focused search queries.
2. **Retrieval** pulls grounded passages from the local corpus (and, if enabled, live
   government sources), embedding and ranking them. A score-floor + shared-term gate decides
   whether there's *enough* grounding to answer — otherwise Lexa abstains.
3. **Drafter** answers using only those passages, citing each inline. A deterministic guard
   drops any citation id the model invents.
4. **Verifier** independently checks each claim against its source and approves, revises, or
   rejects (with a bounded repair loop). Low-confidence answers are labelled as such.

The whole thing **streams** to the UI in real time, so you watch it research, draft, and
verify step by step — nothing is a black box.

## Where the data comes from

**Grounded corpus (bundled, offline):** verbatim public-domain U.S. constitutional
provisions — the Bill of Rights (Amendments I–X) plus the 13th, 14th, 15th, 19th, and 26th
Amendments — each with an accurate citation, effective date, and link to
`constitution.congress.gov`. Inspect exactly what's loaded any time via `GET /meta/sources`.

**Live government sources (optional, real-time):** when enabled, Lexa fetches at query time
from official/free APIs and links each citation back to the authoritative page:

| Source | Key needed | What it provides |
|--------|-----------|------------------|
| **Federal Register** (`federalregister.gov`) | none | US rules, notices, executive & presidential documents |
| **CourtListener** (`courtlistener.com`) | optional token | US court opinions / case law |
| **GovInfo** (`api.govinfo.gov`) | free key | US Code, CFR, bills, and more |

**Bulk ingestion:** `scripts/ingest_courtlistener.py` pulls real opinions into the vector
store for offline retrieval.

> Live connectors require internet, so they run on your machine — not in CI. Their
> request/response handling is unit-tested with mocked responses; a real end-to-end test runs
> with `LIVE_E2E=1 pytest tests/test_live_sources.py`.

## Quick start

No API keys needed — uses the mock provider and an offline embedder.

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open **http://localhost:8000/** for the web app, or **/docs** for the interactive API.

```bash
# register → returns access + refresh tokens
curl -X POST localhost:8000/auth/register -H 'content-type: application/json' \
  -d '{"email":"a@b.com","password":"pw123456","jurisdiction":"US-CA"}'

# ask (use the access token)
curl -X POST localhost:8000/chat/ask -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"question":"What does the First Amendment protect?"}'

# see exactly what the answer can be grounded in
curl localhost:8000/meta/sources
```

## Turning on real reasoning & live data

In `.env`:

```ini
LLM_PROVIDER=live
ANTHROPIC_API_KEY=...                       # and/or OPENAI_API_KEY / GOOGLE_API_KEY
EMBEDDINGS_BACKEND=sentence_transformers    # pip install sentence-transformers (better retrieval)
LIVE_SOURCES_ENABLED=true
LIVE_SOURCES=federal_register,courtlistener
```

Then set the model ids you actually want in `app/config.py` → `MODEL_REGISTRY` (the shipped
ids are placeholders that change over time).

## Configuration

All via environment variables (see `.env.example` for the full list):

| Area | Keys |
|------|------|
| Auth | `JWT_SECRET`, `ACCESS_TOKEN_MINUTES`, `REFRESH_TOKEN_DAYS`, `MIN/MAX_PASSWORD_LENGTH` |
| Storage | `DATABASE_URL`, `VECTOR_STORE_PATH`, `AUTO_CREATE_TABLES` |
| Quotas | `FREE_TIER_QUOTA`, `FREE_TIER_WINDOW_HOURS`, `FREE_TIER_ALLOW_ESCALATION` |
| Models | `LLM_PROVIDER`, `ANTHROPIC/OPENAI/GOOGLE_API_KEY`, `MAX_PROVIDER_RETRIES` |
| Embeddings | `EMBEDDINGS_BACKEND`, `EMBEDDINGS_MODEL`, `EMBEDDINGS_DIM` |
| Grounding | `GROUNDING_FLOOR`, `GROUNDING_STRONG` |
| Live data | `LIVE_SOURCES_ENABLED`, `LIVE_SOURCES`, `COURTLISTENER_TOKEN`, `GOVINFO_API_KEY` |
| Security | `SECURITY_HEADERS_ENABLED`, `FORCE_HTTPS`, `CORS_ORIGINS`, rate-limit settings |
| Email | `EMAIL_BACKEND`, `SMTP_*`, `APP_BASE_URL`, `EMAIL_TOKEN_HOURS` |

## API reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | — | Create account (sends verification email), returns tokens |
| POST | `/auth/login` | — | Log in, returns access + refresh tokens |
| POST | `/auth/refresh` | — | Rotate refresh token → new access + refresh |
| POST | `/auth/logout` | ✓ | Revoke all refresh tokens |
| POST | `/auth/verify-email` | — | Confirm email with a token |
| POST | `/auth/request-password-reset` | — | Email a reset link (always 202; no enumeration) |
| POST | `/auth/reset-password` | — | Set a new password, revokes sessions |
| GET | `/auth/me` | ✓ | Profile + tier + email-verified |
| POST | `/chat/ask` | ✓ | Ask a question → cited, verified answer (single JSON) |
| POST | `/chat/ask/stream` | ✓ | Same, streamed as NDJSON status/token/done events |
| GET | `/chat/conversations` | ✓ | List your conversations |
| GET | `/chat/conversations/{id}` | ✓ | Full thread with citations |
| GET | `/account/export` | ✓ | Download all your data (GDPR/CCPA) |
| DELETE | `/account/` | ✓ | Delete your account and data |
| POST | `/billing/upgrade` | ✓ | Dev stub — replace with Stripe |
| GET | `/meta/sources` | — | What the corpus + live sources are |
| GET | `/health` | — | Status, provider, embeddings, live sources |

Answer responses include `answer`, `citations` (each with `citation`, `text`, `source_url`,
`effective_date`, `relevance`), `verdict` (`approve` / `revise` / `reject` / `abstain`),
`reasoning`, and quota usage.

## Project layout

```
app/
  main.py            app wiring: CORS, security headers, rate limit, logging, errors, static UI
  config.py          settings + MODEL_REGISTRY + tier policy + grounding thresholds
  db.py              users, subscriptions, usage, refresh + email tokens, conversations
  auth.py            hashing, JWT, refresh rotation, email tokens, current-user
  safety.py          disclaimer + scope/refusal guardrails
  ratelimit.py       per-IP sliding-window limiter
  security_headers.py  HSTS/CSP/X-Frame-Options/… middleware
  email.py           pluggable sender (console dev / SMTP prod)
  logging_config.py  structured JSON logs
  rag/               embeddings, vector store, seed corpus, retriever, live_sources
  services/          llm_providers, model_router, agents (pipeline), usage
  routers/           auth, chat, billing, account, meta
frontend/index.html  single-page web app (landing + chat + citation viewer)
scripts/             ingest_courtlistener.py
alembic/             database migrations
tests/               39 tests across rag, pipeline, providers, api, account, live sources
Dockerfile · docker-compose.yml · Procfile · render.yaml · start.sh · .github/workflows/ci.yml
```

## Testing

```bash
pytest -q          # 39 tests
```

Covers retrieval + abstention, the reasoning pipeline, provider JSON parsing and the live
Anthropic/OpenAI/Google adapters (mocked HTTP), the full API (auth, quota → 402, citations,
scope refusal, refresh rotation, streaming, security headers), account flows (verify/reset/
export/delete), the expanded corpus, and the live-source connectors. CI runs the suite and
verifies migrations on every push.

## Database migrations

Dev auto-creates tables. In production, set `AUTO_CREATE_TABLES=false` and use Alembic:

```bash
alembic upgrade head                       # apply
alembic revision --autogenerate -m "msg"   # after editing models
alembic downgrade -1                        # roll back one
```

## Deployment

See **[DEPLOYMENT.md](./DEPLOYMENT.md)** for Render / Docker / Heroku, required env vars, and
the pre-launch checklist. In short: `start.sh` runs migrations then gunicorn + uvicorn workers;
`render.yaml` provisions a web service + Postgres; `Dockerfile`/`docker-compose.yml` cover
containers.

## Security & privacy

bcrypt password hashing; short-lived JWT access tokens with rotating refresh tokens; per-IP
rate limiting; security headers (CSP, HSTS when behind TLS, anti-framing/sniffing); per-user
data isolation; full data **export** and **deletion**; structured audit logs. Lexa does not
use your questions to train models, and the whole stack is self-hostable on your own database
and API keys.

## Honest limitations

- The bundled corpus is constitutional text; broad coverage needs live sources or ingestion of
  a **licensed/lawful** corpus. "No hallucinated law" holds *within retrieved sources*.
- The offline hashing embedder is approximate — use `sentence_transformers` for quality
  retrieval and the cleanest abstention.
- Answers are mock text until you set `LLM_PROVIDER=live` with a model key (retrieval,
  citations, streaming, and abstention are real regardless).
- `/billing/upgrade` is a dev stub — wire Stripe before charging.
- The in-memory rate limiter is single-instance; use Redis across multiple workers.
- Have counsel review disclaimers, data handling, and unauthorized-practice boundaries before
  any real launch.

## Roadmap

See **[ROADMAP.md](./ROADMAP.md)** for the prioritized plan (document upload & analysis,
Stripe billing, evaluation harness for hallucination metrics, team accounts, and more) and
**[AUDIT.md](./AUDIT.md)** for the current code-quality status.

---

<div align="center">
<sub>Lexa is informational only and not a substitute for a licensed attorney.</sub>
</div>
