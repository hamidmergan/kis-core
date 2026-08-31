"""Checks that embedding falls back to the next same-model provider on a hard error."""

import pytest

from src.services.aia_embeddings import FallbackEmbeddingProvider


class _Ok:
    model_name = "bge-m3"

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        return [[0.1, 0.2] for _ in texts]


class _AlwaysFails:
    model_name = "bge-m3"

    def __init__(self, message="Error code: 502 - Bad Gateway"):
        self.calls = 0
        self._message = message

    def embed(self, texts):
        self.calls += 1
        raise RuntimeError(self._message)


def test_primary_success_never_touches_fallback():
    primary, fallback = _Ok(), _Ok()
    provider = FallbackEmbeddingProvider([primary, fallback])

    vectors = provider.embed(["a", "b"])

    assert vectors == [[0.1, 0.2], [0.1, 0.2]]
    assert primary.calls == 1
    assert fallback.calls == 0


def test_primary_failure_falls_back_to_next_provider():
    primary, fallback = _AlwaysFails(), _Ok()
    provider = FallbackEmbeddingProvider([primary, fallback])

    vectors = provider.embed(["a"])

    assert vectors == [[0.1, 0.2]]
    assert primary.calls == 1
    assert fallback.calls == 1


def test_all_providers_failing_raises_the_last_error():
    primary = _AlwaysFails("Error code: 502 - Bad Gateway")
    last = _AlwaysFails("Error code: 503 - Service Unavailable")
    provider = FallbackEmbeddingProvider([primary, last])

    with pytest.raises(RuntimeError, match="503"):
        provider.embed(["a"])

    assert primary.calls == 1
    assert last.calls == 1


def test_model_name_is_the_primarys():
    provider = FallbackEmbeddingProvider([_Ok(), _Ok()])
    assert provider.model_name == "bge-m3"


def test_embed_one_uses_the_base_class_default():
    provider = FallbackEmbeddingProvider([_Ok()])
    assert provider.embed_one("x") == [0.1, 0.2]


def test_needs_at_least_one_provider():
    with pytest.raises(ValueError):
        FallbackEmbeddingProvider([])
