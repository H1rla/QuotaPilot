"""Deterministic task profiling and strict routing-policy tests."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from quotapilot.routing.models import (
    ProfileSource,
    RoutingPolicy,
    TaskClass,
    TaskProfileOverrides,
)
from quotapilot.routing.profiler import TaskProfiler


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ("Fix typo in README", TaskClass.MECHANICAL),
        ("Implement a local parser helper", TaskClass.LOCAL_IMPLEMENTATION),
        ("Debug a race condition", TaskClass.DEBUGGING),
        ("Make a repository-wide refactor", TaskClass.REPOSITORY_CHANGE),
        ("Review the system architecture", TaskClass.ARCHITECTURE),
        ("Review this patch", TaskClass.REVIEW),
        ("Research competing algorithms", TaskClass.RESEARCH),
        ("Do the unusual thing", TaskClass.UNKNOWN),
    ],
)
def test_heuristic_task_classes_are_deterministic(
    summary: str, expected: TaskClass
) -> None:
    profile = TaskProfiler().profile(summary)

    assert profile.task_class is expected
    assert profile.profile_source is ProfileSource.HEURISTIC
    assert profile == TaskProfiler().profile(summary)


def test_partial_override_produces_mixed_profile() -> None:
    profile = TaskProfiler().profile(
        "Fix typo in README", TaskProfileOverrides(complexity=0.8)
    )

    assert profile.complexity == 0.8
    assert profile.task_class is TaskClass.MECHANICAL
    assert profile.profile_source is ProfileSource.MIXED


def test_complete_override_produces_explicit_profile() -> None:
    overrides = TaskProfileOverrides(
        complexity=0.1,
        ambiguity=0.2,
        failure_cost=0.3,
        verifiability=0.4,
        context_demand=0.5,
        latency_sensitivity=0.6,
        task_class=TaskClass.REVIEW,
    )

    profile = TaskProfiler().profile("Anything", overrides)

    assert profile.profile_source is ProfileSource.EXPLICIT
    assert profile.task_class is TaskClass.REVIEW


@pytest.mark.parametrize(
    ("model_type", "data"),
    [
        (RoutingPolicy, {"quota_pressure_weight": "0.3"}),
        (RoutingPolicy, {"escalation_enabled": 1}),
        (RoutingPolicy, {"unknown_setting": 0.2}),
        (TaskProfileOverrides, {"complexity": "0.2"}),
        (TaskProfileOverrides, {"complexity": 1.1}),
        (TaskProfileOverrides, {"typo_field": 0.2}),
    ],
)
def test_routing_configuration_is_strict(
    model_type: type[BaseModel], data: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        model_type.model_validate(data)


def test_routing_policy_rejects_invalid_tolerance_order() -> None:
    with pytest.raises(ValidationError, match="risk_tolerance_reduction"):
        RoutingPolicy(underpower_tolerance=0.05, risk_tolerance_reduction=0.10)
