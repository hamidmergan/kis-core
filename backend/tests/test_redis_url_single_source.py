"""The Redis address is written down once, every other module imports it."""

from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"


def test_no_module_spells_out_a_redis_address():
    treffer = [
        str(p.relative_to(SRC))
        for p in SRC.rglob("*.py")
        if p.name != "redis_url.py" and "redis://" in p.read_text(encoding="utf-8")
    ]
    assert treffer == []


def test_celery_reads_broker_and_result_store_from_the_one_place():
    from src.celery_app import celery_app
    from src.core.redis_url import CELERY_RESULT_URL, REDIS_URL

    assert celery_app.conf.broker_url == REDIS_URL
    assert celery_app.conf.result_backend == CELERY_RESULT_URL
