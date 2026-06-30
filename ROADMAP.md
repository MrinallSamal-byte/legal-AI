# Lexa — Roadmap to a Practical, User-Ready Product

This plan turns the working backend + web app into something real users would choose and
keep using. It is ordered by **user impact first**: the earliest phases remove the reasons
a real person would bounce, the later phases deepen value and scale.

Effort key: **S** ≈ ½–1 day · **M** ≈ 2–4 days · **L** ≈ 1–2 weeks. Effort assumes one
developer and the current codebase.

---

## Where things stand today

Working and tested: auth (JWT + refresh), tiered quotas, cost-aware model routing, the
Researcher→Drafter→Verifier reasoning pipeline, real retrieval over a small public-domain
corpus, provider adapters (key-ready), a single-page web app, rate limiting, structured
logging, Docker. The honest gaps: it answers via a mock until a key is added, the corpus
is tiny, billing is a stub, and there's no streaming, document upload, or account/admin UX.

The phases below close those gaps in the order a user feels them.

---

## Phase 1 — Make the first real session trustworthy (highest priority)

Goal: a new user asks a real question and gets a fast, believable, well-presented answer.

1. **Turn on a real model end-to-end** *(S, unblocks everything)*
   Add your API key, set `LLM_PROVIDER=live`, and put current model ids in `MODEL_REGISTRY`.
   Run a few dozen real questions and read the outputs. *User value:* the product actually
   reasons instead of returning placeholder text.

2. **Streaming responses** *(M)*
   Stream the drafter's answer token-by-token (SSE or chunked) instead of a 10–30s spinner.
   *User value:* perceived speed is the single biggest factor in whether a chat feels alive.
   The verifier verdict and citations attach when the stream completes.

3. **Expand the corpus to something useful** *(M–L)*
   Ingest a meaningful slice of real law for one or two jurisdictions: federal + your launch
   state's statutes and key case law via the CourtListener script, plus public regulations.
   *User value:* answers stop being limited to constitutional basics. This is the core of the
   "real things, no lies" promise — coverage is what makes grounding actually helpful.

4. **Better retrieval quality** *(M)*
   Switch `EMBEDDINGS_BACKEND` to `sentence_transformers` (or a provider embedder), add a
   reranking pass, and tune chunk size. *User value:* the right authority surfaces for
   nuanced questions, not just keyword overlaps.

5. **Citation viewer** *(S–M)*
   Click a citation → side panel shows the exact retrieved passage with the matched text
   highlighted, plus the source link and effective date. *User value:* users can verify
   the answer themselves in two seconds — this is what earns trust in a legal tool.

6. **Conversation history that works** *(S)*
   Wire the existing `conversations`/`messages` tables into the sidebar: load a past thread,
   continue it, rename, delete. *User value:* people return to prior research; losing it is a
   dealbreaker.

7. **Jurisdiction onboarding + per-question override** *(S)*
   A first-run step that sets jurisdiction, and a selector on each question. *User value:*
   law is jurisdiction-specific; getting this wrong makes answers misleading.

---

## Phase 2 — Make it useful for real day-to-day work

Goal: reasons to come back, and the workflows lawyers/laypeople actually need.

8. **Document upload & analysis** *(L)*
   Upload a contract/notice/lease (PDF/DOCX); Lexa extracts text, indexes it for that user,
   and answers questions about *their* document with citations to clauses. *User value:* this
   is the killer use case — "what does this contract say about termination?" beats generic Q&A.

9. **Plain-language vs. professional mode** *(S)*
   A toggle: explain like I'm not a lawyer, or give me the technical analysis with authorities.
   *User value:* serves both audiences without dumbing down or overwhelming.

10. **Guided intake for common tasks** *(M)*
    Templates that ask structured questions ("draft a demand letter", "review a lease",
    "understand a court notice") and produce a structured output. *User value:* most users
    don't know how to phrase a legal question; guide them.

11. **Export & share** *(S)*
    Export an answer (with citations and disclaimer) to PDF/DOCX/email; copy a shareable link.
    *User value:* legal research is rarely the end — people send it to a lawyer, landlord, or
    counterparty.

12. **"Find me a lawyer" handoff** *(S–M)*
    When Lexa hits the scope boundary or the user wants action, offer a clean handoff:
    a summary of their issue + prepared questions they can take to counsel (and optionally a
    referral directory). *User value:* turns the refusal moment into something helpful.

13. **Saved matters / folders** *(M)*
    Group conversations and documents by "matter" (e.g., "apartment dispute"). *User value:*
    real legal problems span many sessions and files.

---

## Phase 3 — Monetization, accounts, and trust at scale

14. **Real billing (Stripe)** *(M)*
    Replace the `/upgrade` stub with Checkout + webhooks that set the tier only on verified
    payment; add a billing portal (update card, cancel, invoices) and proration. *User value:*
    a real upgrade path; *business value:* revenue.

15. **Usage transparency** *(S)*
    Show remaining uses, reset time, and (for paid) a running cost/usage view. *User value:*
    no surprise paywalls; people trust limits they can see.

16. **Email + verification + password reset** *(M)*
    Verify email on signup, password reset by email, optional 2FA. *User value:* table-stakes
    account safety; *business value:* reduces fraud and free-tier abuse.

17. **Team / org accounts** *(L, if B2B)*
    Shared workspaces, seats, role-based access, centralized billing. *User value:* law firms
    and small businesses buy per-team, not per-person.

18. **Trust & safety surface** *(S)*
    Persistent, clear disclaimer; a visible "how Lexa works" explainer (retrieval + verifier +
    abstention); a feedback button on every answer. *User value:* informed users; *and* the
    feedback feeds Phase 4 evaluation.

---

## Phase 4 — Quality, differentiation, and polish

19. **Evaluation harness + hallucination metrics** *(M, do early if you can)*
    A labeled question set; measure abstention rate, verifier catch rate, and citation
    accuracy on every change. *User value (indirect):* you can prove and improve correctness
    instead of guessing — essential for a legal tool.

20. **Answer confidence & "what I'm unsure about"** *(S)*
    Surface the verifier's reasoning and explicitly flag uncertain points. *User value:*
    calibrated trust — users know when to double-check.

21. **Follow-up suggestions & clarifying questions** *(S)*
    When a question is ambiguous, Lexa asks one sharp clarifying question before answering;
    after an answer, it offers logical next questions. *User value:* feels like a competent
    assistant, not a search box.

22. **Multi-jurisdiction / multi-language** *(L)*
    Expand corpora and prompts to more regions and languages. *User value:* reach; *and* legal
    needs are global and underserved.

23. **Mobile-first polish / PWA** *(M)*
    Make the web app installable and genuinely good on a phone. *User value:* most consumer
    legal questions happen on mobile, in the moment.

24. **Voice input / accessibility** *(S–M)*
    Speech-to-text input, screen-reader-correct markup, keyboard nav. *User value:* access for
    people who struggle to phrase legal questions in writing.

---

## Cross-cutting (do continuously, not as one phase)

- **Security:** secrets in a manager (not `.env` in prod), HTTPS/HSTS, rate-limit auth
  endpoints harder, audit log for data access, encrypt sensitive content at rest, data
  export + deletion (GDPR/CCPA). *Legal content is sensitive — this is non-negotiable.*
- **Reliability/observability:** error tracking (Sentry), request tracing, per-request cost
  and latency dashboards, alerting on verifier-reject and abstention spikes.
- **Data infra:** move SQLite → Postgres, the numpy store → pgvector/Qdrant when the corpus
  grows; add DB migrations (Alembic); cache embeddings.
- **Compliance review:** have a lawyer review disclaimers, unauthorized-practice-of-law
  boundaries per jurisdiction, and your data-handling/retention policy **before** public
  launch. This gates go-live, not a "later" item.
- **Cost controls:** per-user spend caps, prompt/response caching for common questions,
  cheaper-model-first with escalation only when the verifier rejects.

---

## Suggested first sprint (2 weeks, maximum user-visible payoff)

If you want the fastest path from "demo" to "people would actually use this":

1. Real model on (1) → 2. Streaming (2) → 3. Citation viewer (5) → 4. Conversation history
   (6) → 5. Jurisdiction onboarding (7) → 6. Start corpus expansion for one jurisdiction (3).

That sequence makes the very first session fast, believable, verifiable, and persistent —
the four things that decide whether someone comes back. Everything else builds on it.

---

## Recommended priority order at a glance

| Priority | Items | Why |
|---|---|---|
| **Now** | 1, 2, 5, 6, 7 | The first session has to feel fast, trustworthy, and not throwaway. |
| **Next** | 3, 4, 8, 11 | Real coverage + the document use case = genuine daily utility. |
| **Then** | 14, 15, 16, 19 | Charge money safely, and measure correctness. |
| **Later** | 9, 10, 12, 13, 17, 20–24 | Depth, differentiation, reach. |
| **Always** | Security, observability, compliance | Sensitive data + legal domain = continuous, not optional. |
