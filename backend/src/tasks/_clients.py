"""The model clients the tool tasks call: the chat model and the image routes."""

from src.services import provider_transport


def _get_llm_client(provider_id: int | None = None):
    from src.services.openai_compat_llm import OpenAICompatLLMClient
    if provider_id is not None:
        from src.services import feature_provider_choices, feature_router
        binding = feature_provider_choices.resolve_binding("chat", provider_id)
        return feature_router.make_llm_client(binding)
    from src.dependencies import _binding_tuple, _resolve_llm_binding
    binding = _resolve_llm_binding()
    api_key, base_url, model, provider = _binding_tuple(binding)
    if not api_key:
        raise RuntimeError("Kein LLM-Provider konfiguriert")
    client = OpenAICompatLLMClient(api_key=api_key, base_url=base_url, model=model, whisper_model=model,
                                   provider=provider, **provider_transport.sdk_clients(binding))
    # The admin route needs the same switches as a chosen provider, a thinking model writes nothing otherwise.
    from src.services import feature_router
    feature_router._attach_model_profile(client, binding)
    return client


def _image_http_client(
    feature: str,
    *,
    provider_id: int | None = None,
    extra_headers: dict | None = None,
    timeout: float = 120.0,
):
    """Builds address, model and client for an image route."""
    import httpx
    from src.services import feature_router

    if provider_id is not None:
        from src.services import feature_provider_choices
        binding = feature_provider_choices.resolve_binding(feature, provider_id)
    else:
        binding = feature_router.resolve(feature)  # raises FeatureNotConfigured

    provider = binding.provider
    base = provider["base_url"].rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"

    headers: dict[str, str] = {}
    api_key = provider.get("api_key")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if extra_headers:
        headers.update(extra_headers)

    # The door takes the seat for every picture and falls back when the first choice does not answer.
    return base, (binding.model or ""), httpx.Client(
        headers=headers, timeout=timeout, transport=provider_transport.transport_for(binding))
