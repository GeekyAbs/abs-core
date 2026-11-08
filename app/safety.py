"""Deterministic input/output checks.

These are deliberately simple: a portfolio bot does not need an LLM-based
guardrail stack, and a remote self-check would add latency and another failure
mode. Patterns are matched against NFKC-normalised text so full-width
characters cannot sidestep them.

The output check is a last line of defence. Secrets should never reach the
model in the first place: the prompt is static and contains no credentials.
"""

import re
import unicodedata
from typing import NamedTuple


class Verdict(NamedTuple):
    allowed: bool
    reason: str


_FLAGS = re.IGNORECASE

_INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(all\s+)?(previous|prior|above)\s+instructions?\b", _FLAGS),
    re.compile(r"\bdisregard\s+(the\s+)?(above|previous|prior|instructions?)\b", _FLAGS),
    re.compile(
        r"\b(reveal|show|print|repeat)\b.{0,30}\b(system\s+prompt|instructions?|prompt)\b", _FLAGS
    ),
    re.compile(r"\bsystem\s+prompt\b", _FLAGS),
    re.compile(r"\b(jailbreak|dan\s+mode|developer\s+mode)\b", _FLAGS),
    re.compile(r"\bbypass\b.{0,30}\b(guardrail|filter|safety|restriction)s?\b", _FLAGS),
    re.compile(r"\brepeat\s+the\s+words\s+above\b", _FLAGS),
)

_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b", _FLAGS),
    re.compile(r"\bsk-or-v1-[A-Za-z0-9]{8,}\b", _FLAGS),
    re.compile(r"\bOPENROUTER_API_KEY\b", _FLAGS),
    re.compile(r"\bapi[_-]?key\s*[:=]", _FLAGS),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", _FLAGS),
)


def _normalise(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


def check_input(text: str) -> Verdict:
    normalised = _normalise(text)
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(normalised):
            return Verdict(False, "prompt-injection")
    return Verdict(True, "")


def check_output(text: str) -> Verdict:
    normalised = _normalise(text)
    for pattern in _SECRET_PATTERNS:
        if pattern.search(normalised):
            return Verdict(False, "secret-leak")
    return Verdict(True, "")
