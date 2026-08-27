"""The fingerprint has to stay stable per model, otherwise the reindex warning sticks."""
from src.services.aia_embeddings import EmbeddingProvider, compute_fingerprint


class _JitteryProvider(EmbeddingProvider):
    """A provider that returns slightly different vectors on every call."""

    def __init__(self, model: str, dim: int) -> None:
        self._model = model
        self._dim = dim
        self._n = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._n += 1
        # tiny per-call jitter ~1e-6, exactly the kind seen in production
        return [[0.006503 + self._n * 1e-6 + i * 1e-9 for i in range(self._dim)]
                for _ in texts]


def test_fingerprint_is_stable_across_calls_despite_vector_jitter():
    p = _JitteryProvider("e5-mistral-7b-instruct", dim=4096)
    assert compute_fingerprint(p) == compute_fingerprint(p)


def test_fingerprint_differs_for_different_model():
    a = _JitteryProvider("e5-mistral-7b-instruct", dim=4096)
    b = _JitteryProvider("bge-m3", dim=4096)
    assert compute_fingerprint(a) != compute_fingerprint(b)


def test_fingerprint_differs_for_different_dimension():
    a = _JitteryProvider("some-model", dim=1024)
    b = _JitteryProvider("some-model", dim=768)
    assert compute_fingerprint(a) != compute_fingerprint(b)
