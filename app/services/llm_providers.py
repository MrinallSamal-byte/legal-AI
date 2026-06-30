"""LLM provider abstraction: MockProvider (offline) and LiveProvider (real REST)."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from ..config import MODEL_REGISTRY, settings
from ..logging_config import get_logger

log = get_logger("lexa.llm")


@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int


def extract_json(text: str) -> dict:
    """Best-effort JSON extraction: handles ```json fences and surrounding prose."""
    if not text:
        return {}
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start, depth = None, 0
        for i, c in enumerate(text):
            if c == "{":
                if start is None:
                    start = i
                depth += 1
            elif c == "}" and start is not None:
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    break
    if candidate is None:
        return {}
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return {}


class BaseProvider:
    def complete(self, model_key: str, system: str, prompt: str,
                 json_mode: bool = False, temperature: float = 0.2) -> LLMResult:
        raise NotImplementedError


class MockProvider(BaseProvider):
    """Deterministic offline stand-in exercising the pipeline's control flow."""

    def complete(self, model_key, system, prompt, json_mode=False, temperature=0.2) -> LLMResult:
        tin = max(1, len((system + prompt).split()))
        fact_ids = re.findall(r"\[([\w\-]+#?\w*)\]", prompt)
        if "VERIFIER" in system:
            has_cite = "[" in prompt and ("amend" in prompt.lower() or "#chunk" in prompt or
                                          any(c.startswith("usconst") for c in fact_ids))
            out = json.dumps({
                "verdict": "approve" if has_cite else "reject",
                "notes": "" if has_cite else "Claims lack citations to retrieved facts.",
                "unsupported_claims": [],
            })
        elif "DRAFTER" in system:
            ids = fact_ids[:2] or ["F1"]
            cites = "".join(f" [{i}]" for i in ids)
            out = json.dumps({
                "reasoning": "Identified the controlling passages and mapped each claim to a retrieved fact.",
                "answer": (f"Based on the retrieved authority, the governing rule is summarized here{cites}. "
                           "Application depends on your specific facts and jurisdiction."),
                "cited_ids": ids,
            })
        elif "RESEARCHER" in system:
            out = json.dumps({
                "issue": "Identify the controlling legal rule for the question.",
                "queries": [prompt[:80], "relevant statutory and constitutional authority"],
            })
        else:
            out = "[mock model output]"
        return LLMResult(text=out, tokens_out=max(1, len(out.split())), tokens_in=tin)


class LiveProvider(BaseProvider):
    """Real API calls via httpx. Requires the relevant API key."""

    def __init__(self):
        import httpx
        self._client = httpx.Client(timeout=settings.request_timeout_seconds)

    def complete(self, model_key, system, prompt, json_mode=False, temperature=0.2) -> LLMResult:
        spec = MODEL_REGISTRY[model_key]
        last_err = None
        for attempt in range(settings.max_provider_retries + 1):
            try:
                if spec.provider == "anthropic":
                    return self._anthropic(spec.model_id, system, prompt, temperature)
                if spec.provider in ("openai", "oss"):
                    return self._openai(spec.model_id, system, prompt, json_mode, temperature)
                if spec.provider == "google":
                    return self._google(spec.model_id, system, prompt, temperature)
                raise ValueError(f"Unknown provider: {spec.provider}")
            except Exception as e:  # noqa: BLE001
                last_err = e
                log.warning("provider call failed", extra={"extra_fields": {
                    "provider": spec.provider, "attempt": attempt, "error": str(e)}})
                time.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"Provider {spec.provider} failed after retries: {last_err}")

    def _anthropic(self, model_id, system, prompt, temperature) -> LLMResult:
        r = self._client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.anthropic_api_key,
                     "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model_id, "max_tokens": 2048, "temperature": temperature,
                  "system": system, "messages": [{"role": "user", "content": prompt}]},
        )
        r.raise_for_status()
        data = r.json()
        text = "".join(b.get("text", "") for b in data.get("content", []))
        u = data.get("usage", {})
        return LLMResult(text, u.get("input_tokens", 0), u.get("output_tokens", 0))

    def _openai(self, model_id, system, prompt, json_mode, temperature) -> LLMResult:
        body = {"model": model_id, "temperature": temperature,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": prompt}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = self._client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"}, json=body)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        u = data.get("usage", {})
        return LLMResult(text, u.get("prompt_tokens", 0), u.get("completion_tokens", 0))

    def _google(self, model_id, system, prompt, temperature) -> LLMResult:
        r = self._client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
            f"?key={settings.google_api_key}",
            json={"system_instruction": {"parts": [{"text": system}]},
                  "contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": temperature}})
        r.raise_for_status()
        data = r.json()
        cand = data["candidates"][0]["content"]["parts"][0]["text"]
        u = data.get("usageMetadata", {})
        return LLMResult(cand, u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0))


_provider: BaseProvider | None = None


def get_provider() -> BaseProvider:
    global _provider
    if _provider is None:
        _provider = LiveProvider() if settings.llm_provider == "live" else MockProvider()
    return _provider
