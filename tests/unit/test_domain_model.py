from quotapilot.domain.model import AIModel


def test_aimodel_defaults() -> None:
    model = AIModel(id="gpt-5-codex", provider="openai-codex")

    assert model.selectable is True
    assert model.supported_efforts == ()
    assert model.relative_power is None
    assert model.metadata == {}


def test_aimodel_preserves_unknown_metadata() -> None:
    model = AIModel(
        id="mystery-model",
        provider="openai-codex",
        metadata={"routing_status": "unknown", "raw": {"vendor_field": 42}},
    )

    assert model.metadata["routing_status"] == "unknown"
    assert model.metadata["raw"]["vendor_field"] == 42
