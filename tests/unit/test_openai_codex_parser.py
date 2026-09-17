"""Fixture-driven tests for the OpenAI Codex parser/normalizer.

Fixtures live in tests/fixtures/openai_codex/ (see PROVENANCE.md there for
which are live-sanitized vs. synthetic-but-schema-conformant). These tests
never touch the network or a real `codex` process.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from quotapilot.providers.openai_codex.errors import CodexNormalizationError
from quotapilot.providers.openai_codex.models import (
    GetAccountRateLimitsResponse,
    GetAccountResponse,
    ModelListResponse,
    parse_codex_response,
)
from quotapilot.providers.openai_codex.parser import (
    normalize_account,
    normalize_capabilities,
    normalize_models,
    normalize_quota_bindings,
    normalize_quota_pools,
)
from quotapilot.providers.openai_codex.redaction import redact

FIXTURES = Path(__file__).parent.parent / "fixtures" / "openai_codex"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _rate_limits(name: str) -> GetAccountRateLimitsResponse:
    return _rate_limits_from_dict(_load(name))


def _rate_limits_from_dict(raw: dict) -> GetAccountRateLimitsResponse:
    return parse_codex_response(
        GetAccountRateLimitsResponse, raw, context="account/rateLimits/read"
    )


def _account(name: str) -> GetAccountResponse:
    return parse_codex_response(GetAccountResponse, _load(name), context="account/read")


def test_raw_observation_redaction_handles_key_variants_and_containers() -> None:
    raw = {
        "access_token": "live-token",
        "clientSecret": "live-secret",
        "authorization": "Bearer live-token",
        "credentials": {"futureUnknownKey": "live-value"},
        "nested": {"session-id": "live-session", "catalogVersion": "v1"},
    }

    redacted = redact(raw)

    assert redacted["access_token"] == "REDACTED"
    assert redacted["clientSecret"] == "REDACTED"
    assert redacted["authorization"] == "REDACTED"
    assert redacted["credentials"] == "REDACTED"
    assert redacted["nested"]["session-id"] == "REDACTED"
    assert redacted["nested"]["catalogVersion"] == "v1"


# --- rate limits / quota pools -------------------------------------------------


def test_single_window_normalizes_percent_to_fraction() -> None:
    response = _rate_limits("rate_limits_single_window.json")
    pools = normalize_quota_pools(response)

    assert len(pools) == 1
    pool = pools[0]
    assert pool.id == "codex:primary"
    assert pool.provider == "openai-codex"
    # Not provider-confirmed semantics -> "unknown", not a guessed value.
    assert pool.kind == "unknown"
    assert pool.scope == "unknown"
    assert pool.used_fraction == pytest.approx(0.65)
    assert pool.remaining_fraction == pytest.approx(0.35)
    assert pool.applies_to_models == ()
    assert pool.window_seconds == 10080 * 60
    assert pool.resets_at == datetime.fromtimestamp(1893456000, tz=UTC)
    # windowDurationMins IS present here, so starts_at can be derived.
    assert pool.starts_at == datetime.fromtimestamp(1893456000 - 10080 * 60, tz=UTC)


def test_quota_pool_provenance_records_basis_and_evidence() -> None:
    response = _rate_limits("rate_limits_single_window.json")
    pool = normalize_quota_pools(response)[0]

    provenance = pool.metadata["provenance"]
    assert provenance["kind"]["basis"] == "unknown"
    assert provenance["scope"]["basis"] == "unknown"
    assert "evidence" in provenance["kind"]
    assert "evidence" in provenance["scope"]


def test_multi_window_produces_two_model_scoped_pools() -> None:
    response = _rate_limits("rate_limits_multi_window.json")
    pools = normalize_quota_pools(response)

    assert {p.id for p in pools} == {
        "codex-gpt-6-astra:primary",
        "codex-gpt-6-astra:secondary",
    }
    for pool in pools:
        # normal_model_slug IS a provider-declared field -> scope is confirmed.
        assert pool.scope == "model"
        assert pool.kind == "unknown"
        assert pool.applies_to_models == ("gpt-6-astra",)
        assert pool.metadata["provenance"]["scope"]["basis"] == "provider"

    primary = next(p for p in pools if p.id.endswith(":primary"))
    secondary = next(p for p in pools if p.id.endswith(":secondary"))
    assert primary.used_fraction == pytest.approx(0.20)
    assert secondary.used_fraction == pytest.approx(0.95)


def test_bindings_derived_from_model_scoped_pools() -> None:
    response = _rate_limits("rate_limits_multi_window.json")
    pools = normalize_quota_pools(response)
    bindings = normalize_quota_bindings(pools)

    assert len(bindings) == 1
    binding = bindings[0]
    assert binding.model_id == "gpt-6-astra"
    # A binding QuotaPilot constructed over provider data is "observed",
    # not "provider" -- there is no first-class provider binding fact.
    assert binding.confidence == "observed"
    assert binding.metadata["provenance"]["basis"] == "inferred"
    assert set(binding.quota_pool_ids) == {
        "codex-gpt-6-astra:primary",
        "codex-gpt-6-astra:secondary",
    }


def test_bindings_only_reference_pools_in_same_list() -> None:
    response = _rate_limits("rate_limits_multi_window.json")
    pools = normalize_quota_pools(response)
    bindings = normalize_quota_bindings(pools)

    pool_ids = {p.id for p in pools}
    for binding in bindings:
        assert set(binding.quota_pool_ids) <= pool_ids


def test_account_wide_pool_has_no_binding() -> None:
    response = _rate_limits("rate_limits_single_window.json")
    pools = normalize_quota_pools(response)
    bindings = normalize_quota_bindings(pools)

    assert bindings == []


def test_unknown_quota_category_and_unknown_fields_do_not_crash() -> None:
    response = _rate_limits("rate_limits_unknown_fields.json")
    pools = normalize_quota_pools(response)

    assert len(pools) == 1
    pool = pools[0]
    assert pool.id == "future-quota-category-not-yet-seen:primary"
    assert pool.raw_name == "Some Future Category"
    assert pool.used_fraction == pytest.approx(0.12)
    # Unknown nested fields are preserved, not dropped.
    assert pool.metadata["raw_snapshot"]["primary"]["futureWindowField"] == (
        "some-new-value-not-yet-modeled"
    )
    assert pool.metadata["raw_snapshot"]["rateLimitReachedType"] == (
        "some_new_reason_not_previously_documented"
    )


def test_bucket_with_no_windows_still_produces_a_pool() -> None:
    response = _rate_limits("rate_limits_no_windows.json")
    pools = normalize_quota_pools(response)

    assert len(pools) == 1
    pool = pools[0]
    assert pool.id == "credits-only:unrepresented"
    assert pool.kind == "unknown"
    assert pool.scope == "unknown"
    assert pool.used_fraction is None
    assert pool.remaining_fraction is None
    # The credits data is not lost even though there's no window to hang it on.
    assert pool.metadata["raw_snapshot"]["credits"]["hasCredits"] is True


def test_missing_window_duration_leaves_starts_at_none() -> None:
    response = _rate_limits("rate_limits_no_duration.json")
    pools = normalize_quota_pools(response)

    assert len(pools) == 1
    pool = pools[0]
    assert pool.resets_at is not None
    assert pool.window_seconds is None
    assert pool.starts_at is None


def test_zero_duration_is_accepted_as_degenerate_window() -> None:
    raw = _load("rate_limits_single_window.json")
    raw["rateLimits"]["primary"]["windowDurationMins"] = 0
    raw["rateLimitsByLimitId"] = None
    response = _rate_limits_from_dict(raw)

    pool = normalize_quota_pools(response)[0]

    assert pool.window_seconds == 0
    assert pool.starts_at == pool.resets_at


def test_zero_timestamp_parses_without_inventing_a_sentinel() -> None:
    raw = _load("rate_limits_single_window.json")
    raw["rateLimits"]["primary"]["resetsAt"] = 0
    raw["rateLimitsByLimitId"] = None
    response = _rate_limits_from_dict(raw)

    pool = normalize_quota_pools(response)[0]

    assert pool.resets_at == datetime.fromtimestamp(0, tz=UTC)


def test_timestamp_overflow_raises_typed_normalization_error() -> None:
    raw = _load("rate_limits_single_window.json")
    huge = 10**18
    raw["rateLimits"]["primary"]["resetsAt"] = huge
    raw["rateLimitsByLimitId"] = None
    response = _rate_limits_from_dict(raw)

    with pytest.raises(CodexNormalizationError):
        normalize_quota_pools(response)


def test_negative_duration_raises_typed_normalization_error() -> None:
    raw = _load("rate_limits_single_window.json")
    raw["rateLimits"]["primary"]["windowDurationMins"] = -5
    raw["rateLimitsByLimitId"] = None
    with pytest.raises(CodexNormalizationError):
        _rate_limits_from_dict(raw)


@pytest.mark.parametrize("bad_value", ["1893456000", True, 1893456000.0, -1])
def test_strict_reset_timestamp_rejects_malformed_values(bad_value: object) -> None:
    raw = _load("rate_limits_single_window.json")
    raw["rateLimits"]["primary"]["resetsAt"] = bad_value
    raw["rateLimitsByLimitId"] = None

    with pytest.raises(CodexNormalizationError):
        _rate_limits_from_dict(raw)


@pytest.mark.parametrize("bad_value", ["60", True, 65.0, -1])
def test_strict_window_duration_rejects_malformed_values(bad_value: object) -> None:
    raw = _load("rate_limits_single_window.json")
    raw["rateLimits"]["primary"]["windowDurationMins"] = bad_value
    raw["rateLimitsByLimitId"] = None

    with pytest.raises(CodexNormalizationError):
        _rate_limits_from_dict(raw)


def test_malformed_percent_raises_typed_normalization_error() -> None:
    with pytest.raises(CodexNormalizationError):
        _rate_limits("rate_limits_malformed_percent.json")


@pytest.mark.parametrize(
    ("bad_value", "case_id"),
    [
        (-5, "negative"),
        (101, "greater-than-100"),
        ("65", "string"),
        (True, "bool"),
        (65.0, "float"),
        (None, "null"),
    ],
    ids=lambda v: v if isinstance(v, str) else repr(v),
)
def test_strict_used_percent_rejects_malformed_values(bad_value: object, case_id: str) -> None:
    raw = _load("rate_limits_single_window.json")
    raw["rateLimits"]["primary"]["usedPercent"] = bad_value
    raw["rateLimitsByLimitId"]["codex"]["primary"]["usedPercent"] = bad_value

    with pytest.raises(CodexNormalizationError):
        _rate_limits_from_dict(raw)


@pytest.mark.parametrize("used_percent", [0, 100])
def test_boundary_percentages_are_valid(used_percent: int) -> None:
    raw = _load("rate_limits_single_window.json")
    raw["rateLimits"]["primary"]["usedPercent"] = used_percent
    raw["rateLimitsByLimitId"] = None
    response = _rate_limits_from_dict(raw)

    pools = normalize_quota_pools(response)

    assert len(pools) == 1
    assert pools[0].used_fraction == pytest.approx(used_percent / 100.0)
    assert pools[0].remaining_fraction == pytest.approx(1.0 - used_percent / 100.0)


def test_multiple_rate_limit_buckets_all_produce_pools() -> None:
    single = _load("rate_limits_single_window.json")
    multi = _load("rate_limits_multi_window.json")
    combined = copy.deepcopy(single)
    combined["rateLimitsByLimitId"]["codex-gpt-6-astra"] = multi["rateLimitsByLimitId"][
        "codex-gpt-6-astra"
    ]
    response = _rate_limits_from_dict(combined)

    pools = normalize_quota_pools(response)

    assert {p.id for p in pools} == {
        "codex:primary",
        "codex-gpt-6-astra:primary",
        "codex-gpt-6-astra:secondary",
    }


# --- account / capabilities -----------------------------------------------------


def test_chatgpt_account_maps_plan_name() -> None:
    account_response = _account("account_read.json")
    rate_limits_response = _rate_limits("rate_limits_single_window.json")
    models = normalize_models(
        parse_codex_response(ModelListResponse, _load("model_list.json"), context="model/list")
    )
    capabilities = normalize_capabilities(models, account_response, rate_limits_response)

    account = normalize_account(
        account_response,
        rate_limits_response,
        capabilities,
        observed_at=datetime.now(UTC),
    )

    assert account.provider == "openai-codex"
    assert account.plan_name == "synthetic-plan"
    assert account.account_id == "acct_redacted_1"
    assert account.capabilities.metadata["account_type"] == "chatgpt"


@pytest.mark.parametrize(
    ("fixture_name", "expected_account_type"),
    [
        ("account_read_apikey.json", "apiKey"),
        ("account_read_bedrock.json", "amazonBedrock"),
    ],
)
def test_non_chatgpt_account_variants_have_no_plan_name(
    fixture_name: str, expected_account_type: str
) -> None:
    account_response = _account(fixture_name)
    capabilities = normalize_capabilities([], account_response, None)

    account = normalize_account(
        account_response, None, capabilities, observed_at=datetime.now(UTC)
    )

    assert account.plan_name is None
    assert account.account_id is None
    assert account.capabilities.metadata["account_type"] == expected_account_type


def test_null_account_does_not_crash() -> None:
    account_response = _account("account_read_null_account.json")
    capabilities = normalize_capabilities([], account_response, None)

    account = normalize_account(
        account_response, None, capabilities, observed_at=datetime.now(UTC)
    )

    assert account.plan_name is None
    assert "account_type" not in account.capabilities.metadata


def test_normalize_models_preserves_reasoning_efforts_and_hidden_flag() -> None:
    models = normalize_models(
        parse_codex_response(ModelListResponse, _load("model_list.json"), context="model/list")
    )

    assert len(models) == 6
    default_model = next(m for m in models if m.metadata["is_default"])
    assert default_model.id == "gpt-6-astra"
    assert "ultra" in default_model.supported_efforts
    assert default_model.selectable is True
    selectable_provenance = default_model.metadata["provenance"]["selectable"]
    assert selectable_provenance["source"] == "model/list.hidden"
    assert selectable_provenance["basis"] == "inferred"
    assert selectable_provenance["confidence"] == "high"
    assert all(m.provider == "openai-codex" for m in models)


def test_capabilities_reflect_live_discovery() -> None:
    models = normalize_models(
        parse_codex_response(ModelListResponse, _load("model_list.json"), context="model/list")
    )
    account_response = _account("account_read.json")
    rate_limits_response = _rate_limits("rate_limits_single_window.json")

    capabilities = normalize_capabilities(models, account_response, rate_limits_response)

    assert capabilities.supports_reasoning_effort is True
    assert capabilities.supports_model_selection is True
    # `credits` key is present (hasCredits=false, but the mechanism exists).
    assert capabilities.supports_credits is True
    provenance = capabilities.metadata["provenance"]
    assert provenance["supports_model_selection"]["source"] == "model/list.data[].hidden"
    assert provenance["supports_model_selection"]["basis"] == "inferred"
    assert provenance["supports_model_selection"]["confidence"] == "medium"
    assert provenance["supports_credits"]["source"] == "account/rateLimits/read.*.credits"
    assert provenance["supports_credits"]["basis"] == "inferred"
    assert provenance["supports_credits"]["confidence"] == "medium"
