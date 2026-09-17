from datetime import datetime

import pytest
from pydantic import ValidationError

from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel


def _capabilities() -> CapabilitySet:
    return CapabilitySet(
        models=(AIModel(id="gpt-5-codex", provider="openai-codex"),),
        supports_reasoning_effort=True,
    )


def test_account_info_valid() -> None:
    account = AccountInfo(
        provider="openai-codex",
        account_id="acct_123",
        plan_name="pro",
        capabilities=_capabilities(),
        observed_at=datetime.now().astimezone(),
    )

    assert account.plan_name == "pro"
    assert account.capabilities.supports_reasoning_effort is True


def test_account_info_requires_aware_datetime() -> None:
    with pytest.raises(ValidationError):
        AccountInfo(
            provider="openai-codex",
            capabilities=_capabilities(),
            observed_at=datetime.now(),  # noqa: DTZ005 - intentionally naive for the test
        )


def test_account_info_allows_missing_optional_fields() -> None:
    account = AccountInfo(
        provider="openai-codex",
        capabilities=_capabilities(),
        observed_at=datetime.now().astimezone(),
    )

    assert account.account_id is None
    assert account.plan_name is None
