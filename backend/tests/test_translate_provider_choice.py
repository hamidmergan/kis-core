"""The translation picker only offers providers that answer right now."""


async def test_translate_config_hides_unreachable(monkeypatch):
    from src.routes import translate
    from src.services import feature_provider_choices

    anbieter = [{"id": 92, "name": "HPC"}, {"id": 21, "name": "THL myLab"}]
    monkeypatch.setattr("src.dependencies.get_translation_providers", lambda: anbieter)

    async def fake_reachable(provider):
        return provider["id"] != 92

    monkeypatch.setattr(feature_provider_choices, "_is_reachable", fake_reachable)

    result = await translate.get_translate_config(current_user={}, locale="de")
    assert result["providers"] == [{"id": 21, "label": "THL myLab"}]
