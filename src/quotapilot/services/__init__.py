"""Thin glue layer: wires providers to persistence (and, later, budget/routing).

No policy (budget math, routing decisions) belongs here — only orchestration
of calls into `quotapilot.providers`/`quotapilot.history`.
"""
