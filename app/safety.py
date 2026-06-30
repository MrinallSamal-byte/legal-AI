"""Scope guardrails and the standard legal disclaimer."""
from __future__ import annotations

import re

DISCLAIMER = (
    "This is general legal information, not legal advice, and does not create an "
    "attorney-client relationship. Laws vary by jurisdiction and change over time. "
    "For your specific situation, consult a licensed attorney in your jurisdiction."
)

_REFUSE_PATTERNS = [
    r"\brepresent me\b", r"\bbe my (lawyer|attorney)\b", r"\bfile (this|my|it) (for|on)\b",
    r"\bsign (this|on my behalf)\b", r"\bappear in court\b", r"\bact as my (lawyer|attorney)\b",
    r"\bsubmit (this )?to the court\b", r"\bserve (this|the) (papers|documents|complaint)\b",
]
_REFUSE_RE = re.compile("|".join(_REFUSE_PATTERNS), re.IGNORECASE)


def requires_licensed_professional(question: str) -> bool:
    return bool(_REFUSE_RE.search(question or ""))


def refusal_message() -> str:
    return (
        "I can't take real-world legal actions or represent you - that requires a "
        "licensed attorney. I can explain the relevant law, outline your options, and "
        "help you prepare questions or documents to bring to one. " + DISCLAIMER
    )
