"""Turns the markdown of one page into embedded chunks, skipping pages whose text did not change."""
from typing import Callable

from src.features.campus.repository import chunks as chunk_repo
from src.features.campus.repository import pages as page_repo
from src.features.campus.services.chunking import split_markdown
from src.features.campus.services.extract import content_hash

EmbedFn = Callable[[list[str]], list[list[float]]]

_EMBED_BATCH = 32


def index_markdown(page_id: int, title: str | None, markdown: str, embed: EmbedFn, force: bool = False) -> int:
    """Returns the number of chunks written, 0 when the page was unchanged."""
    digest = content_hash(markdown)
    page = page_repo.get_page(page_id)
    if page is None:
        return 0
    if not force and page.get("content_hash") == digest and page.get("status") == "ready":
        return 0
    pieces = split_markdown(markdown)
    if not pieces:
        page_repo.set_page_status(page_id, "failed", "no text")
        return 0
    ids = chunk_repo.replace_chunks(page_id, pieces)
    texts = [p["content"] for p in pieces]
    for start in range(0, len(texts), _EMBED_BATCH):
        batch_ids = ids[start:start + _EMBED_BATCH]
        vectors = embed(texts[start:start + _EMBED_BATCH])
        chunk_repo.set_embeddings(list(zip(batch_ids, vectors)))
    page_repo.set_page_indexed(page_id, digest, title, len(ids))
    return len(ids)


def embedder() -> EmbedFn:
    """The embedding route of the admin, with its fallback provider."""
    from src.services.aia_embeddings import get_embedding_provider_with_fallback
    provider = get_embedding_provider_with_fallback()
    return provider.embed
