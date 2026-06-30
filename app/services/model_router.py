"""Maps (tier, task, user preference) -> a concrete model key from MODEL_REGISTRY."""
from __future__ import annotations

from ..config import MODEL_REGISTRY, TIERS, settings


def pick_model(tier_name: str, task: str = "answer", preference: str | None = None) -> str:
    tier = TIERS[tier_name]
    if tier.allow_model_choice and preference:
        spec = MODEL_REGISTRY.get(preference)
        if spec and spec.tier_label == "premium":
            return preference
    return tier.verifier_model if task == "verify" else tier.default_model


def escalate(tier_name: str, current_key: str) -> str | None:
    if tier_name == "free" and not settings.free_tier_allow_escalation:
        return None
    ladder = ["oss-flash", "mid", "premium-a"]
    if current_key in ladder and current_key != ladder[-1]:
        return ladder[ladder.index(current_key) + 1]
    return None
