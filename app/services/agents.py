"""Multi-agent reasoning pipeline: Researcher -> Drafter -> Verifier with repair loop."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from ..config import MODEL_REGISTRY
from ..logging_config import get_logger
from ..safety import DISCLAIMER
from ..rag.retriever import GroundedFact, get_retriever, is_grounded
from .llm_providers import BaseProvider, extract_json
from .model_router import escalate, pick_model

log = get_logger("lexa.agents")
MAX_REPAIRS = 2

RESEARCHER_SYS = (
    "You are the RESEARCHER in a legal research system. Read the user's question and the "
    "stated jurisdiction. Spot the legal issue, then produce focused search queries to "
    "find controlling authority. Do NOT answer the question. "
    'Return JSON: {"issue": "<one sentence>", "queries": ["q1", "q2", "q3"]}.'
)

DRAFTER_SYS = (
    "You are the DRAFTER in a legal research system. Answer the user's question using ONLY "
    "the GROUNDED FACTS provided - each has an id like [usconst-amend-1]. Reason step by "
    "step: (1) restate the issue, (2) for each legal claim you make, identify which fact id "
    "supports it, (3) write the answer with an inline [id] after every sentence that states "
    "law. Never assert a legal rule that no provided fact supports; if the facts are "
    "insufficient, say so explicitly. Do not invent case names, sections, or dates. "
    'Return JSON: {"reasoning": "<your step-by-step analysis>", "answer": "<final answer '
    'with inline [id] citations>", "cited_ids": ["id1", "id2"]}.'
)

VERIFIER_SYS = (
    "You are the VERIFIER, an independent adversarial checker. You are given a DRAFT answer "
    "and the GROUNDED FACTS. Your job is to catch errors, not to be agreeable. Check: "
    "(1) does every sentence stating law cite a fact id that actually appears in the facts? "
    "(2) does the cited fact's text genuinely support (entail) the claim, or is it a stretch? "
    "(3) are there invented citations, case names, sections, or dates not in the facts? "
    "Approve only if every legal claim is supported. Otherwise revise (fixable) or reject. "
    'Return JSON: {"verdict": "approve|revise|reject", "notes": "<problems and fixes>", '
    '"unsupported_claims": ["..."]}.'
)


@dataclass
class PipelineResult:
    answer: str
    citations: list[dict]
    verdict: str
    model_used: str
    reasoning: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_estimate: float = 0.0
    abstained: bool = False
    trace: list[str] = field(default_factory=list)


def _cost(model_key: str, tin: int, tout: int) -> float:
    s = MODEL_REGISTRY[model_key]
    return (tin / 1_000_000) * s.input_cost + (tout / 1_000_000) * s.output_cost


def _facts_blob(facts: list[GroundedFact]) -> str:
    return "\n".join(
        f"[{f.id}] {f.text} (source: {f.citation}; effective {f.effective_date}; "
        f"relevance {f.score})" for f in facts
    )


def _chunk_for_stream(text: str, words_per_chunk: int = 4) -> Iterator[str]:
    words = text.split(" ")
    for i in range(0, len(words), words_per_chunk):
        yield " ".join(words[i:i + words_per_chunk]) + (" " if i + words_per_chunk < len(words) else "")


def pipeline_events(provider: BaseProvider, question: str, jurisdiction: str,
                    tier_name: str, preference: str | None = None):
    trace: list[str] = []
    tin = tout = 0
    cost = 0.0

    def call(model_key, system, prompt, json_mode=True):
        nonlocal tin, tout, cost
        r = provider.complete(model_key, system, prompt, json_mode=json_mode)
        tin += r.tokens_in
        tout += r.tokens_out
        cost += _cost(model_key, r.tokens_in, r.tokens_out)
        return r

    answer_model = pick_model(tier_name, "answer", preference)
    verify_model = pick_model(tier_name, "verify", preference)

    yield "status", {"stage": "researching", "label": "Spotting the legal issue"}
    res = extract_json(call(answer_model, RESEARCHER_SYS,
                            f"Question: {question}\nJurisdiction: {jurisdiction}").text)
    queries = res.get("queries") or [question]
    trace.append(f"researcher: issue={res.get('issue','?')[:60]!r}, {len(queries)} queries")

    yield "status", {"stage": "retrieving", "label": "Searching legal sources"}
    retriever = get_retriever()
    best: dict[str, GroundedFact] = {}
    for q in [question, *queries]:
        for f in retriever.retrieve(q, jurisdiction, k=4):
            if f.id not in best or f.score > best[f.id].score:
                best[f.id] = f
    facts = sorted(best.values(), key=lambda f: -f.score)[:6]
    trace.append(f"retriever: {len(facts)} grounded facts")
    yield "status", {"stage": "grounded", "label": f"Found {len(facts)} relevant passages",
                     "facts": len(facts)}

    if not is_grounded(question, facts):
        text = ("I couldn't find authoritative support for this in my sources, so I won't "
                "guess. You may want a jurisdiction-specific primary source or a licensed "
                "attorney. " + DISCLAIMER)
        for ch in _chunk_for_stream(text):
            yield "token", {"text": ch}
        yield "result", PipelineResult(
            answer=text, citations=[], verdict="abstain", model_used=answer_model,
            tokens_in=tin, tokens_out=tout, cost_estimate=round(cost, 6),
            abstained=True, trace=trace)
        return

    blob = _facts_blob(facts)
    by_id = {f.id: f for f in facts}
    draft, verdict, notes, reasoning = {}, "reject", "", ""
    current_model = answer_model

    for attempt in range(MAX_REPAIRS + 1):
        yield "status", {"stage": "drafting",
                         "label": "Drafting" if attempt == 0 else "Revising with reviewer notes"}
        d = extract_json(call(current_model, DRAFTER_SYS,
            f"Question: {question}\nJurisdiction: {jurisdiction}\n\nGROUNDED FACTS:\n{blob}\n\n"
            f"Reviewer notes to address: {notes or 'none'}").text)
        draft = d
        reasoning = d.get("reasoning", "")
        trace.append(f"drafter[{attempt}] model={current_model} cited={d.get('cited_ids', [])}")

        claimed = [i for i in d.get("cited_ids", []) if i in by_id]

        yield "status", {"stage": "verifying", "label": "Verifying every claim against sources"}
        v = extract_json(call(verify_model, VERIFIER_SYS,
            f"DRAFT ANSWER: {d.get('answer','')}\n"
            f'"cited_ids": {claimed}\n\nGROUNDED FACTS:\n{blob}').text)
        verdict = v.get("verdict", "reject")
        notes = v.get("notes", "")
        trace.append(f"verifier[{attempt}] verdict={verdict}")

        if verdict == "approve":
            break
        stronger = escalate(tier_name, current_model)
        if stronger:
            current_model = stronger
            trace.append(f"escalated -> {current_model}")

    cited = [{"id": i, "citation": by_id[i].citation, "text": by_id[i].text,
              "source_url": by_id[i].source_url, "effective_date": by_id[i].effective_date,
              "relevance": by_id[i].score}
             for i in draft.get("cited_ids", []) if i in by_id]

    answer_text = draft.get("answer", "")
    if verdict != "approve":
        answer_text = ("[Low confidence - the verifier could not fully confirm this answer "
                       "against sources; treat it as a starting point only]\n\n" + answer_text)
    answer_text = (answer_text or "").strip() + "\n\n" + DISCLAIMER

    yield "status", {"stage": "answering", "label": "Writing the answer"}
    for ch in _chunk_for_stream(answer_text):
        yield "token", {"text": ch}

    yield "result", PipelineResult(
        answer=answer_text, citations=cited, verdict=verdict, model_used=current_model,
        reasoning=reasoning, tokens_in=tin, tokens_out=tout, cost_estimate=round(cost, 6),
        abstained=False, trace=trace)


def run_pipeline(provider: BaseProvider, question: str, jurisdiction: str,
                 tier_name: str, preference: str | None = None) -> PipelineResult:
    result: PipelineResult | None = None
    for kind, payload in pipeline_events(provider, question, jurisdiction, tier_name, preference):
        if kind == "result":
            result = payload
    assert result is not None, "pipeline_events must yield a result"
    return result
