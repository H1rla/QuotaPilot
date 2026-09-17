"""Typed errors for the OpenAI Codex provider boundary.

Kept separate from `quotapilot.providers.openai_codex.rpc` so that transport
failures, RPC-level failures, and normalization failures are distinguishable
by callers without inspecting exception messages (which never contain
secrets).
"""

from __future__ import annotations


class CodexProviderError(Exception):
    """Base for all OpenAI Codex provider-boundary errors."""


class CodexTransportError(CodexProviderError):
    """The `codex app-server` process/transport failed below the RPC layer.

    Covers: process startup failure, a broken pipe or other read/write I/O
    failure, malformed framing (a line that is not valid JSON), EOF (the
    process closed its stdout), unexpected app-server termination, and RPC
    call timeouts. Distinct from `CodexRpcError`, which means the transport
    worked fine and the peer returned a well-formed JSON-RPC error object.
    """


class CodexRpcError(CodexProviderError):
    """`codex app-server` returned a well-formed JSON-RPC error response.

    Carries `method`, the JSON-RPC `code`, and `message` only. The
    JSON-RPC error object's `data` field is deliberately never exposed here
    (or logged) — a backend could put arbitrary, potentially sensitive
    context there, and QuotaPilot has no way to verify its contents are
    safe to surface.
    """

    def __init__(self, *, method: str, code: int, message: str) -> None:
        super().__init__(f"{method} returned JSON-RPC error {code}: {message}")
        self.method = method
        self.code = code
        self.message = message


class CodexNormalizationError(CodexProviderError):
    """A Codex response could not be turned into a valid domain object.

    Raised for: invalid provider response structure (fails raw-model
    validation), invalid/unrepresentable timestamps (e.g. overflow),
    invalid percentages (out of range or wrong type), pagination protocol
    violations (cursor cycles, page-limit exceeded), and any other domain
    conversion failure. This is intentional: QuotaPilot must fail
    explicitly here rather than silently clamp or guess.
    """
