"""Checks the warm-up of the evidence caches during the stream."""
from src.features.ai_assistant.routes._evidence import _AttributionPrewarmer


def fake_embed(texts):
    # deterministic 1-d vector per text; length distinguishes them
    return [[float(len(t)), float(sum(map(ord, t[:3])))] for t in texts]


def fake_search(line, vec):
    return [{"id": line, "vec": vec}]


async def test_feed_and_flush_populates_vecs_and_hits():
    pw = _AttributionPrewarmer(fake_embed, fake_search)
    line = "Der Kurs startet im April und die Abgabe erfolgt im Juli."
    pw.feed_line(line)
    assert pw.pending_count() > 0
    await pw.flush()
    assert line in pw.vecs
    assert line in pw.hits
    assert pw.hits[line] == [{"id": line, "vec": pw.vecs[line]}]
    assert pw.pending_count() == 0


async def test_non_candidate_line_is_skipped():
    pw = _AttributionPrewarmer(fake_embed, fake_search)
    pw.feed_line("## Überblick")   # heading: dedup key < 16 chars -> not a candidate
    pw.feed_line("   ")             # blank
    assert pw.pending_count() == 0


async def test_multi_sentence_prose_caches_each_sentence_too():
    pw = _AttributionPrewarmer(fake_embed, fake_search)
    line = "Der Kurs startet im April. Die Abgabe erfolgt im Juli."
    pw.feed_line(line)
    await pw.flush()
    # whole line AND each sentence sub-unit are cached (mirrors _attribution_subunits)
    assert line in pw.vecs
    assert "Der Kurs startet im April." in pw.vecs
    assert "Die Abgabe erfolgt im Juli." in pw.vecs


async def test_repeated_line_is_embedded_once():
    calls = []

    def counting_embed(texts):
        calls.append(list(texts))
        return fake_embed(texts)

    pw = _AttributionPrewarmer(counting_embed, fake_search)
    line = "Ein ganzer Satz mit genug Inhalt zum Zitieren."
    pw.feed_line(line)
    pw.feed_line(line)   # duplicate
    await pw.flush()
    # the line appears in exactly one embed batch, once
    flat = [t for batch in calls for t in batch]
    assert flat.count(line) == 1


async def test_flush_empty_is_noop():
    pw = _AttributionPrewarmer(fake_embed, fake_search)
    await pw.flush()
    assert pw.vecs == {} and pw.hits == {}


async def test_embed_failure_does_not_raise_and_leaves_caches_empty():
    def boom(texts):
        raise RuntimeError("embed provider down")

    pw = _AttributionPrewarmer(boom, fake_search)
    pw.feed_line("Ein ganzer Satz mit genug Inhalt zum Zitieren.")
    await pw.flush()   # must swallow the failure
    assert pw.vecs == {} and pw.hits == {}


async def test_two_flushes_accumulate_across_batches():
    pw = _AttributionPrewarmer(fake_embed, fake_search)
    pw.feed_line("Erster vollständiger Satz mit Inhalt hier.")
    await pw.flush()
    pw.feed_line("Zweiter vollständiger Satz mit Inhalt dort.")
    await pw.flush()
    assert "Erster vollständiger Satz mit Inhalt hier." in pw.vecs
    assert "Zweiter vollständiger Satz mit Inhalt dort." in pw.vecs


async def test_flushes_counter_tracks_embed_calls_only_when_work_done():
    # The counter only advances on a non-empty pass.
    pw = _AttributionPrewarmer(fake_embed, fake_search)
    await pw.flush()                 # nothing pending
    assert pw.flushes == 0
    pw.feed_line("Ein vollständiger Satz mit genug Inhalt hier.")
    await pw.flush()
    assert pw.flushes == 1
    await pw.flush()                 # nothing new pending
    assert pw.flushes == 1
