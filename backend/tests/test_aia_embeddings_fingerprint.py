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


def test_ollama_schreibweise_gilt_als_gleiches_modell():
    # Local 08.10.: Ollama names it qwen3-embedding:4b, GWDG qwen3-embedding-4b, same index.
    from src.services.aia_embeddings import same_embedding_space
    gwdg = compute_fingerprint(_JitteryProvider("qwen3-embedding-4b", dim=2560))
    ollama = compute_fingerprint(_JitteryProvider("qwen3-embedding:4b", dim=2560))
    assert same_embedding_space(gwdg, ollama)


def test_anderes_modell_oder_andere_groesse_bleibt_verschieden():
    from src.services.aia_embeddings import same_embedding_space
    basis = compute_fingerprint(_JitteryProvider("qwen3-embedding-4b", dim=2560))
    assert not same_embedding_space(basis, compute_fingerprint(_JitteryProvider("qwen3-embedding:8b", dim=2560)))
    assert not same_embedding_space(basis, compute_fingerprint(_JitteryProvider("qwen3-embedding-4b", dim=1024)))
