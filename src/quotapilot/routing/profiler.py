"""Small deterministic task profiler used when explicit values are absent."""

from __future__ import annotations

from dataclasses import dataclass

from quotapilot.routing.models import (
    ProfileSource,
    TaskClass,
    TaskProfile,
    TaskProfileOverrides,
)


@dataclass(frozen=True)
class _HeuristicProfile:
    task_class: TaskClass
    complexity: float
    ambiguity: float
    failure_cost: float
    verifiability: float
    context_demand: float
    latency_sensitivity: float


_PROFILES = {
    TaskClass.MECHANICAL: _HeuristicProfile(
        TaskClass.MECHANICAL, 0.15, 0.10, 0.15, 0.95, 0.10, 0.80
    ),
    TaskClass.LOCAL_IMPLEMENTATION: _HeuristicProfile(
        TaskClass.LOCAL_IMPLEMENTATION, 0.45, 0.30, 0.35, 0.75, 0.40, 0.50
    ),
    TaskClass.DEBUGGING: _HeuristicProfile(
        TaskClass.DEBUGGING, 0.75, 0.55, 0.65, 0.45, 0.75, 0.35
    ),
    TaskClass.REPOSITORY_CHANGE: _HeuristicProfile(
        TaskClass.REPOSITORY_CHANGE, 0.70, 0.50, 0.65, 0.50, 0.85, 0.35
    ),
    TaskClass.ARCHITECTURE: _HeuristicProfile(
        TaskClass.ARCHITECTURE, 0.90, 0.75, 0.90, 0.25, 0.90, 0.20
    ),
    TaskClass.RESEARCH: _HeuristicProfile(
        TaskClass.RESEARCH, 0.70, 0.70, 0.55, 0.35, 0.65, 0.25
    ),
    TaskClass.REVIEW: _HeuristicProfile(
        TaskClass.REVIEW, 0.55, 0.40, 0.65, 0.70, 0.65, 0.35
    ),
    TaskClass.UNKNOWN: _HeuristicProfile(
        TaskClass.UNKNOWN, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50
    ),
}

_SIGNALS: tuple[tuple[TaskClass, tuple[str, ...]], ...] = (
    (TaskClass.ARCHITECTURE, ("architecture", "architect", "system design")),
    (
        TaskClass.REPOSITORY_CHANGE,
        ("repository-wide", "repo-wide", "cross-module", "migration", "refactor"),
    ),
    (
        TaskClass.DEBUGGING,
        ("debug", "race condition", "deadlock", "root cause", "investigate bug"),
    ),
    (TaskClass.REVIEW, ("review", "audit", "critique", "assess")),
    (TaskClass.RESEARCH, ("research", "literature", "compare approaches")),
    (
        TaskClass.MECHANICAL,
        ("typo", "rename", "format", "spelling", "readme", "whitespace"),
    ),
    (
        TaskClass.LOCAL_IMPLEMENTATION,
        ("implement", "add ", "fix ", "update ", "change "),
    ),
)

_NUMERIC_FIELDS = (
    "complexity",
    "ambiguity",
    "failure_cost",
    "verifiability",
    "context_demand",
    "latency_sensitivity",
)


class TaskProfiler:
    """Produce repeatable approximate task dimensions without an LLM."""

    def profile(
        self, summary: str, overrides: TaskProfileOverrides | None = None
    ) -> TaskProfile:
        task_class = self._classify(summary)
        heuristic = _PROFILES[task_class]
        values = {field: getattr(heuristic, field) for field in _NUMERIC_FIELDS}

        explicit_fields: set[str] = set()
        if overrides is not None:
            for field in _NUMERIC_FIELDS:
                value = getattr(overrides, field)
                if value is not None:
                    values[field] = value
                    explicit_fields.add(field)
            if overrides.task_class is not None:
                task_class = overrides.task_class
                explicit_fields.add("task_class")

        if not explicit_fields:
            source = ProfileSource.HEURISTIC
        elif explicit_fields == {*_NUMERIC_FIELDS, "task_class"}:
            source = ProfileSource.EXPLICIT
        else:
            source = ProfileSource.MIXED

        return TaskProfile(
            summary=summary,
            task_class=task_class,
            tags=(f"class:{task_class.value}",),
            profile_source=source,
            **values,
        )

    @staticmethod
    def _classify(summary: str) -> TaskClass:
        normalized = " ".join(summary.lower().split())
        for task_class, signals in _SIGNALS:
            if any(signal in normalized for signal in signals):
                return task_class
        return TaskClass.UNKNOWN
