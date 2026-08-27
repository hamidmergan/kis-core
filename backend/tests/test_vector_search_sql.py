"""The vector arm has to stay in the form that uses the index."""
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
    # A different model would mean re-embedding and rebuilding the index.
    assert _EMBED_INDEX_DIM == 2560
