# Lexa — Legal AI Assistant

Grounded, cited legal research with tiered models and an independent verification step.
Lexa retrieves real source text, drafts an answer that cites it, and a verifier checks
every claim before the user sees it. It abstains ("I couldn't find authoritative support")
rather than inventing law, and it is explicit that it is **not** a lawyer.

See [`DESIGN.md`](./DESIGN.md) for the full architecture and rationale.

## What's implemented

- **Auth** — register/login, bcrypt hashing, JWT access tokens + rotating refresh tokens, logout/revocation, password policy.
- **Tiered usage** — free tier (3–5 uses/window, configurable), Plus, Pro. Quota enforced from the DB; Pro can pick a premium model per request.
- **Cost-aware routing** — `MODEL_REGISTRY` + tier policy choose the model; free tier defaults to the cheapest, escalation gated by config.
- **Multi-agent reasoning** — Researcher → Drafter → Verifier with a bounded repair loop. Real step-by-step legal-reasoning prompts; an adversarial verifier does entailment checking; a deterministic guard drops any citation id the model invents.
- **Real RAG** — a persistent vector store (cosine search) with pluggable embedders (offline hashing for tests, sentence-transformers or provider embeddings for production), a verifiable public-domain seed corpus (verbatim U.S. constitutional provisions), and an ingestion script for real court opinions.
- **Web app** — single-page frontend (signup/login, chat, citations panel, usage meter, upgrade flow) served by the API.
- **Provider adapters** — Anthropic, OpenAI, Google via REST, with timeout, retries, and tolerant JSON parsing. Runs offline with a mock provider when no key is set.
- **Production plumbing** — CORS, per-IP rate limiting, structured JSON logging, global error handling, Dockerfile + docker-compose (Postgres), a pytest suite.

## Quick start (no API keys needed)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://localhost:8000/ for the web app, or http://localhost:8000/docs for the API.
Out of the box it uses the **mock provider** (so the pipeline runs with no keys) and the
**offline hashing embedder** (so retrieval works with no model download).

## Turn on real reasoning

In `.env`:

```
LLM_PROVIDER=live
ANTHROPIC_API_KEY=...        # and/or OPENAI_API_KEY / GOOGLE_API_KEY
EMBEDDINGS_BACKEND=sentence_transformers   # real semantic search (pip install sentence-transformers)
```

Then add `MODEL_REGISTRY` ids in `app/config.py` that match the current models you want
to use (the shipped ids are placeholders).

## Add real case law

```bash
python -m scripts.ingest_courtlistener --query "qualified immunity" --pages 2
```

Pulls opinions from CourtListener (a free public legal database), chunks, embeds, and
indexes them. Needs outbound network access, so run it on your own machine.

## Tests

```bash
pytest -q
```

Covers the RAG retrieval and abstention, the reasoning pipeline, provider JSON parsing,
the live Anthropic/OpenAI/Google adapters (mocked HTTP), and the full API (auth, quota →
402, citations, scope refusal, refresh-token rotation, streaming, Pro model choice).

## Database migrations (Alembic)

For local/dev, tables are auto-created on startup. For production, set
`AUTO_CREATE_TABLES=false` and manage the schema with Alembic:

```bash
alembic upgrade head        # apply migrations (creates all tables)
alembic revision --autogenerate -m "describe change"   # after editing models
alembic downgrade -1        # roll back one revision
```

The Alembic env reads `DATABASE_URL` from your settings, so it targets the same database
as the app.

## Layout

```
app/
  main.py            app wiring: CORS, rate limit, logging, errors, static frontend
  config.py          settings + MODEL_REGISTRY + tier policy
  db.py              users, subscriptions, usage, refresh tokens, conversations
  auth.py            hashing, JWT, refresh-token rotation, current-user
  safety.py          disclaimer + scope/refusal guardrails
  ratelimit.py       per-IP sliding-window limiter
  logging_config.py  structured JSON logs
  rag/               embeddings, vector store, seed corpus, retriever
  services/          llm_providers, model_router, agents (pipeline), usage
  routers/           auth, chat, billing
frontend/index.html  single-page web app
scripts/             ingest_courtlistener.py
tests/               test_rag, test_pipeline, test_providers, test_api
Dockerfile, docker-compose.yml
```

## Honest limitations

- The shipped corpus is small (public-domain constitutional text) plus whatever you
  ingest. "No hallucinated law" holds only within retrieved sources — coverage is on you.
- Model ids in `MODEL_REGISTRY` are placeholders; set them to current models.
- `/billing/upgrade` is a dev stub; wire it to Stripe (Checkout + webhook) for real billing.
- Before any real-world launch, have counsel review disclaimers, data handling, and
  unauthorized-practice-of-law boundaries for your jurisdictions.

> Lexa provides general legal information, not legal advice, and is not a substitute for a
> licensed attorney.
