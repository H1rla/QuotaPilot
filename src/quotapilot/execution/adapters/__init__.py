"""Execution adapter protocol and built-in adapters."""

from quotapilot.execution.adapters.base import ExecutionAdapter
from quotapilot.execution.adapters.codex_cli import CodexCliExecutionAdapter

__all__ = ["CodexCliExecutionAdapter", "ExecutionAdapter"]
