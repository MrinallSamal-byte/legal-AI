# Lexa — Legal AI Assistant

**Design & Architecture Document**

Lexa is an AI system that helps users with legal questions and document work. Its core promise is *accuracy over confidence*: every substantive answer is grounded in real sources, carries citations, and is checked by a verification agent before it reaches the user. Lexa never fabricates statutes, case names, or citations, and it is always explicit that it is not a lawyer.

---

## 1. Product principles

1. **No invented law.** Answers are grounded in retrieved source text (RAG). If a claim cannot be grounded, Lexa says so rather than guessing.
2. **Citations always.** Every legal assertion links to a source passage. Unsupported sentences are flagged or removed by the verifier.
3. **Honest about limits.** Lexa is a research assistant, not a substitute for a licensed attorney. A clear disclaimer accompanies legal output, and Lexa refuses tasks that require a licensed professional (e.g., "represent me," "file this for me").
4. **Cost-aware tiering.** Free users get a small number of high-quality but cheaper-to-serve answers; paying users choose premium reasoning models.
5. **Errors reduced by a team, not a single model.** A multi-agent pipeline (research → draft → verify) catches mistakes a single pass would miss.

---

## 2. High-level architecture

```
                     ┌──────────────┐
   Client (web/app)  │   Frontend   │
                     └──────┬───────┘
                            │ HTTPS / JWT
                     ┌──────▼───────┐
                     │   API (FastAPI)│
                     │  auth · billing│
                     │  rate/usage    │
                     └──────┬─────────┘
                            │
              ┌─────────────▼──────────────┐
              │     Orchestrator           │
              │  (multi-agent pipeline)    │
              └──┬───────┬─────────┬───────┘
                 │       │         │
        ┌────────▼─┐ ┌───▼────┐ ┌──▼────────┐
        │Researcher│ │Drafter │ │ Verifier  │
        │ + RAG    │ │        │ │ (critic)  │
        └────┬─────┘ └───┬────┘ └─────┬─────┘
             │           │            │
        ┌────▼───────────▼────────────▼────┐
        │     Model Router (by tier)        │
        │  free → cheap/OSS · paid → premium│
        └────┬──────────────────────────────┘
             │
   ┌─────────▼─────────────────────────────┐
   │ Provider adapters                      │
   │ Anthropic · OpenAI · Google · OSS/vLLM │
   └────────────────────────────────────────┘

   Stores: Postgres (users, subs, usage, conversations)
           Vector DB (legal corpus embeddings)
```

---

## 3. Tiers, usage limits, and billing

| Tier | Price | Quota | Default reasoning model | Verifier model | Model choice |
|------|-------|-------|------------------------|----------------|--------------|
| **Free** | $0 | 3–5 actions / period (configurable) | Cheap / OSS reasoning model (e.g., Gemini Flash class, or a hosted open-source model via vLLM) | Same cheap model, second pass | No |
| **Plus** | paid | Higher quota | Mid-tier premium | Premium | Limited |
| **Pro** | paid | High / soft-unlimited | User picks premium (e.g., Opus-class, GPT-class) | Premium | Yes |

Notes on the table:

- "3–5 actions" is enforced per rolling period (default: 5 per 24h) and is a single config value (`FREE_TIER_QUOTA`). An "action" = one completed pipeline run, not one model call — so the multi-agent overhead does not consume extra user quota.
- Model names in the table are *examples and placeholders*. Provider model identifiers change over time, so Lexa stores them in config (`MODEL_REGISTRY`) and never hardcodes them in business logic. Swap the registry to adopt new models without code changes.
- Billing is handled by a payment provider (Stripe in the scaffold). Webhooks update the user's `subscription.tier` and `subscription.status`. The app treats the DB as the source of truth for entitlements; it never trusts the client.

### Quota enforcement flow

1. Request arrives → auth middleware resolves the user.
2. Usage service checks `count(usage_log WHERE user=u AND created_at > window_start)` against the tier quota.
3. If over quota → `402 Payment Required` with an upgrade message; nothing is charged to the model providers.
4. If allowed → pipeline runs; on success, one `usage_log` row is written atomically.

---

## 4. Model routing (cost → reasoning)

The router maps `(tier, task_type, user_preference)` → a concrete model id from `MODEL_REGISTRY`. Goals:

- **Free tier minimizes cost** by defaulting to the cheapest model that still passes the verifier. If the verifier rejects an answer twice, the request is downgraded gracefully (it tells the user the answer is low-confidence) rather than silently escalating to an expensive model — escalation on the free tier is a config flag, off by default, to protect margins.
- **Paid tiers maximize reasoning quality** and let Pro users explicitly choose a premium model per request.
- Each model entry carries metadata: `provider`, `model_id`, `input_cost`, `output_cost`, `context_window`, `supports_tools`. The router can therefore pick the cheapest model meeting a minimum capability bar.

---

## 5. Multi-agent pipeline (the "team")

A single model answering legal questions in one pass is the main source of hallucinated citations. Lexa splits the work so each step is checkable:

1. **Researcher** — turns the user's question into retrieval queries, pulls candidate passages from the vector DB (legal corpus), and returns a set of *grounded facts*, each tied to a source id + span. No prose answer yet.
2. **Drafter** — writes the answer using *only* the grounded facts. Every sentence that states law must reference a fact id. It may not introduce new legal claims.
3. **Verifier (critic)** — independently checks the draft against the grounded facts:
   - Does every legal claim cite a real, retrieved passage?
   - Does the cited passage actually support the claim (entailment check)?
   - Any hallucinated case names, sections, or dates?
   - Returns `approve`, `revise` (with notes), or `reject`.
4. **Repair loop** — on `revise`, the drafter rewrites with the verifier's notes (bounded retries, default 2). On `reject` after retries, Lexa returns a partial/low-confidence answer with an explicit warning rather than a confident wrong answer.

This reduces error rates because the verifier is an *adversarial second opinion* that only has to catch mistakes, which is easier than producing a perfect answer in one shot. On the free tier the same model plays drafter and verifier (still helpful — self-critique catches many errors); on paid tiers the verifier can be a different, stronger model for independence.

### Why this lowers error rate (intuition)

If a single pass has error probability `p`, an independent verifier that catches a fraction `c` of those errors reduces the residual rate toward `p·(1−c)`. Independence (different model/prompt) raises `c`. The RAG grounding step further shrinks `p` itself by removing the model's need to recall law from memory.

---

## 6. Anti-hallucination / accuracy strategy

- **Retrieval-grounded answers (RAG).** The model answers from retrieved text, not memory. The corpus must be real legal sources you have the right to use (e.g., public statutes, regulations, official court opinions, your own licensed content).
- **Mandatory citations.** Output schema requires a `citations` array; the verifier rejects claims without support.
- **Entailment check.** The verifier confirms each cited passage actually supports the sentence, not just that a citation exists.
- **Abstention.** When grounding is insufficient, Lexa says "I couldn't find authoritative support for this" instead of inventing it. Abstention is treated as a success, not a failure.
- **Jurisdiction awareness.** Law varies by jurisdiction; the user's jurisdiction is captured and passed to retrieval and to the disclaimer.
- **Freshness.** Corpus documents carry `effective_date`/`last_updated`; the verifier warns when authority may be outdated.

---

## 7. Auth & security

- Email + password with bcrypt/argon2 hashing; JWT access tokens (short-lived) + refresh tokens. OAuth providers can be added later.
- Entitlements come from the DB, never the token claims alone (tokens can be stale after a downgrade).
- Rate limiting at the edge in addition to per-user quota.
- PII / legal content is sensitive: encrypt at rest, scope conversations to the owning user, and offer deletion. (Compliance posture — e.g., handling of confidential legal info — should be reviewed by counsel before launch.)
- Secrets (provider API keys, JWT secret, Stripe keys) come from environment/secret manager, never the repo.

---

## 8. Data model (core tables)

- **users** — id, email, password_hash, created_at, jurisdiction.
- **subscriptions** — user_id, tier (`free|plus|pro`), status, provider_customer_id, current_period_end.
- **usage_log** — id, user_id, action_type, model_used, tokens_in/out, cost_estimate, created_at. (Powers quota + cost analytics.)
- **conversations / messages** — scoped to user; store grounded facts + citations for auditability.
- **documents / chunks** — the legal corpus and its embeddings (in the vector store).

---

## 9. Safety & scope guardrails

Lexa **does**: explain legal concepts, summarize statutes/cases from the corpus, draft general-purpose document templates, surface relevant authority with citations, and flag when a licensed professional is needed.

Lexa **does not**: claim to be a lawyer, form an attorney–client relationship, give jurisdiction-specific advice it cannot ground, or take real-world legal actions (filing, representation). These are refused with a referral to seek licensed counsel.

Every legal response carries a short disclaimer: *informational only, not legal advice, not a substitute for a licensed attorney in your jurisdiction.*

---

## 10. What the scaffold in this repo implements

The accompanying code is a runnable FastAPI skeleton that demonstrates the architecture end-to-end with a **mock provider** (so it runs with no API keys):

- JWT auth (register/login).
- Tiered usage limiting with the free-tier quota.
- Config-driven `MODEL_REGISTRY` and tier→model router.
- Multi-agent pipeline (researcher → drafter → verifier with a repair loop) and a RAG stub returning citations.
- Safety disclaimer + scope refusal.
- A smoke test exercising the pipeline.

Swap the mock provider for real Anthropic/OpenAI/Google/OSS adapters and point the RAG stub at a real vector DB + licensed corpus to move toward production.

---

## 11. Roadmap to production (honest checklist)

- [ ] Replace mock provider with real adapters + streaming.
- [ ] Real vector DB (pgvector/Qdrant/Weaviate) + a *licensed* legal corpus with jurisdiction + effective dates.
- [ ] Stripe integration + webhooks + entitlement sync.
- [ ] Evaluation harness: a labeled set of legal Q&A to measure hallucination rate and the verifier's catch rate before/after changes.
- [ ] Human-in-the-loop review for high-stakes outputs.
- [ ] Legal/compliance review of disclaimers, data handling, and unauthorized-practice-of-law boundaries (jurisdiction-specific).
- [ ] Observability: per-request cost, latency, abstention rate, verifier reject rate.
