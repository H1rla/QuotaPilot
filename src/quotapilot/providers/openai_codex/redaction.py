"""Redaction policy for raw provider observations kept in capture metadata.

`parser.py` preserves otherwise-unmodeled/unknown provider structure inside
`QuotaPool.metadata["raw_snapshot"]` and `UsageSnapshot.metadata["raw_observation"]`
so future parser versions can reinterpret it. Those envelopes are *not* the
same thing as QuotaPilot's own structured fields (`AccountInfo.account_id`,
etc.) — they exist purely to avoid silently dropping data QuotaPilot does
not yet understand, so they are redacted defensively before being attached,
independent of whether the structured fields already carry the real value
elsewhere.

Policy: walk the structure recursively; normalize mapping keys by removing
case and separators, then replace the entire value under a known-sensitive
key with a fixed placeholder. Structure outside sensitive containers is
preserved so the envelope stays useful for future re-parsing. This is
intentionally a denylist over known-sensitive key *names*, not a content
scanner — it mirrors the same policy manually applied when this project's
fixtures were sanitized (see tests/fixtures/openai_codex/PROVENANCE.md), now
made permanent and applied automatically to every live capture, not just
fixture generation.
"""

from __future__ import annotations

from typing import Any

SENSITIVE_KEYS = frozenset(
    {
        "email",
        "accountid",
        "account_id",
        "installationid",
        "orgid",
        "organizationid",
        "workspaceid",
        "userid",
        "token",
        "accesstoken",
        "refreshtoken",
        "idtoken",
        "apikey",
        "sessionid",
        "threadid",
        "authorization",
        "password",
        "secret",
        "clientsecret",
        "credential",
        "credentials",
        "cookie",
        "setcookie",
    }
)

_REDACTED_PLACEHOLDER = "REDACTED"


def redact(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact known-sensitive mapping keys; preserve structure otherwise."""
    normalized_key = "".join(character for character in (key or "").lower() if character.isalnum())
    if normalized_key in SENSITIVE_KEYS and value is not None:
        return _REDACTED_PLACEHOLDER
    if isinstance(value, dict):
        return {k: redact(v, key=k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item, key=key) for item in value]
    return value
