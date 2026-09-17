from datetime import datetime

from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel
from quotapilot.domain.quota import QuotaBinding, QuotaPool
from quotapilot.domain.usage import UsageSnapshot


def test_usage_snapshot_composes_domain_objects() -> None:
    now = datetime.now().astimezone()

    account = AccountInfo(
        provider="openai-codex",
        capabilities=CapabilitySet(models=(AIModel(id="gpt-5-codex", provider="openai-codex"),)),
        observed_at=now,
    )
    pool = QuotaPool(
        id="weekly",
        provider="openai-codex",
        kind="rolling",
        scope="account",
        used_fraction=0.5,
    )
    binding = QuotaBinding(
        model_id="gpt-5-codex",
        quota_pool_ids=("weekly",),
        confidence="observed",
    )

    snapshot = UsageSnapshot(
        account=account,
        quota_pools=(pool,),
        quota_bindings=(binding,),
        captured_at=now,
    )

    assert snapshot.quota_pools[0].id == "weekly"
    assert snapshot.quota_bindings[0].quota_pool_ids == ("weekly",)
    assert snapshot.metadata == {}
