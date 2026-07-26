"""The vector branch of hybrid_search_chunks must stay in the index-using form.

aia_chunks.embedding is 2560-dim, over pgvector's 2000-dim limit for a `vector`
index, so the hnsw index is built on `embedding::halfvec(2560)` as a PARTIAL index
(predicate vector_dims=2560). For the planner to actually pick it, the query MUST
cast to halfvec AND carry the same predicate. These guards lock that form so a later
edit cannot silently drop back to a full-scan. Recall equivalence itself is verified
on real data by backend/scripts/spike_hnsw_index.py.
"""
from src.features.ai_assistant.repository.chunks import _vector_search_sql, _EMBED_INDEX_DIM


def test_casts_to_halfvec_so_the_hnsw_index_is_usable():
    sql = _vector_search_sql("")
    assert f"::halfvec({_EMBED_INDEX_DIM})" in sql


def test_carries_the_partial_index_predicate():
    sql = _vector_search_sql("")
    assert f"vector_dims(c.embedding) = {_EMBED_INDEX_DIM}" in sql


def test_keeps_cosine_distance_and_top_80():
    sql = _vector_search_sql("")
    assert "<=>" in sql          # cosine distance operator
    assert "AS distance" in sql  # callers read vec_distance from this
    assert "LIMIT 80" in sql     # RRF fusion still sees the top 80


def test_interpolates_the_source_filter():
    sql = _vector_search_sql("AND s.id = ANY(%s)")
    assert "AND s.id = ANY(%s)" in sql


def test_embed_index_dim_matches_the_model():
    # The current global embedding model (qwen3-embedding-4b) produces 2560-dim vectors.
    # Changing the model means re-embedding AND rebuilding the index for the new dim.
    assert _EMBED_INDEX_DIM == 2560
