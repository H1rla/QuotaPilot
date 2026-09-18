"""Small output redactor for bounded external-agent summaries."""

from __future__ import annotations

import re

_TOKEN_PATTERNS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{12,}"),
)
_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_ -]?key|access[_ -]?token|authorization|password|secret|cookie)"
    r"(\s*[:=]\s*)(\S+)"
)


def redact_output(value: str) -> str:
    """Redact common credential forms without inspecting the environment."""
    redacted = value
    for pattern in _TOKEN_PATTERNS:
        redacted = pattern.sub("REDACTED", redacted)
    return _ASSIGNMENT.sub(r"\1\2REDACTED", redacted)
