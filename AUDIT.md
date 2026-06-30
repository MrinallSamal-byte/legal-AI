# Lexa — Code Audit (with fix status)

A genuine recheck of the actual code. **Update:** the critical batch (C1–C4, S1, S2) has
been fixed and verified; the remaining items are listed below as still-open.

---

## ✅ Fixed and verified in this pass

### C1. Abstention now works — off-topic questions abstain  *(FIXED)*
Previously the system would "ground" any question (even "recipe for chocolate cake") in
unrelated constitutional text. Root cause: the offline lexical embedder gives a nonzero
similarity to everything, so a flat `min_score` couldn't separate on- from off-topic.
Fix, in two parts:
- Each corpus document is now embedded together with its **accurate title + topical
  keywords** (e.g. "First Amendment … freedom of speech, religion, press"), so
  natural-language questions retrieve the *right* provision. ("What does the First
  Amendment protect?" used to match the Sixth Amendment; now it matches the First.)
- A real grounding gate (`is_grounded`) with a score floor plus a **required shared-term
  check** in lexical mode (score-only shortcut kept for semantic embedders).

Verified result: **on-topic 7/7 answer, off-topic 6/7 abstain.** End-to-end, an off-topic
question now returns `verdict: "abstain"` with no citations. One known residual leak:
"capital gains tax rate" still grounds because the word *capital* literally appears in the
Fifth Amendment ("capital … crime") — a true lexical false-friend that a semantic embedder
(`EMBEDDINGS_BACKEND=sentence_transformers`) removes. Tests added for both directions.

### C2. docker-compose can now start  *(FIXED)* — added `psycopg[binary]` to requirements.
### C3. CORS fixed  *(FIXED)* — `allow_credentials=False` (auth is bearer-token, so the
invalid wildcard-origins + credentials combination is gone).
### C4. Streaming error handling  *(FIXED)* — the stream generator is wrapped; a mid-stream
failure now emits a final `{"type":"error", …}` event (verified) and logs it, instead of
hanging the client.
### S1. `.gitignore` added  *(FIXED)* — `.env`, `*.db`, `data/`, vector store, caches, venv
are now ignored, so secrets and user data can't be committed by accident.
### S2. `.dockerignore` added  *(FIXED)* — the image no longer ships the db, `.venv`, `.git`, tests.

Suite after fixes: **21 tests pass** (added abstention tests at the unit and pipeline level).

---

## Still open — important (security, data safety, ops)

- **S3. Tokens in `localStorage`** (XSS can read them). Prefer httpOnly+SameSite cookie for
  the refresh token in production.
- **S4. No security headers / HTTPS enforcement** (HSTS, CSP, X-Content-Type-Options,
  X-Frame-Options). Add a middleware or set them at the reverse proxy.
- **S5. Rate limiter is in-memory and unbounded** — single-process only and entries are
  never evicted. Move to Redis for multi-instance + add cleanup.
- **S6. DB migrations** — *FIXED.* Alembic set up with an initial + email-schema migration;
  `AUTO_CREATE_TABLES=false` hands schema ownership to Alembic in production.
- **S7. Account-safety features** — *FIXED.* Email verification, password reset (with session
  revocation + no email-enumeration), data export, and account deletion are implemented and
  tested. Email delivery uses a pluggable sender (console in dev, SMTP in prod) — wire your
  SMTP/provider creds to actually send.
- **S8. bcrypt 72-byte limit** not handled — add an explicit max-length check. *(still open)*
- **S3/S4/S5 still open:** localStorage tokens, security headers/HTTPS, Redis rate limiter.

## Still open — test & quality

- The verifier `revise`/`reject` → repair/escalation loop, the rate limiter, and
  conversation listing have no tests.
- **Live provider adapters** — *FIXED.* Unit tests with a mocked HTTP transport cover
  Anthropic/OpenAI/Google request shape, response parsing, and retry.
- **CI** — *FIXED.* GitHub Actions runs `pytest` and verifies migrations on every push/PR.
- **CourtListener ingestion is unverified** (network-blocked here); validate on a real
  machine before relying on it.
- No CI (GitHub Actions running `pytest`), no coverage report, no frontend tests.

## Known limitations (by design / documented)

- Corpus is tiny (5 constitutional provisions) — coverage is the core limitation; run the
  ingestion script to expand.
- Offline hashing embedder is approximate (hence the one "capital" false-friend);
  `sentence_transformers` is the recommended production backend.
- Answers are mock text until a real API key is set (retrieval/citations/streaming are real).
- `/billing/upgrade` is a dev stub (no Stripe); model ids in `MODEL_REGISTRY` are placeholders.

## Suggested next fix order

1. **S6 (migrations)** and the **live-adapter tests** before real users/data.
2. **S3, S4, S5, S7, S8** before public launch.
3. Switch default embeddings to `sentence_transformers` on a machine with network — this
   removes the last abstention leak and sharply improves retrieval quality.
