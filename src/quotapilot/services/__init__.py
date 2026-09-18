"""Thin glue layer for provider, persistence, budget, and routing composition.

No policy (budget math, routing decisions) belongs here — only orchestration
of calls into `quotapilot.providers`/`quotapilot.history`.
"""
