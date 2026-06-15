from src.features.ai_assistant.scheduling.fair_dispatch import (
    QueuedJob,
    select_next_dispatches,
)


def _job(jid: str, uid: int, t: float) -> QueuedJob:
    return QueuedJob(job_id=jid, user_id=uid, created_at=t)


def test_no_free_slots_returns_empty():
    q = [_job("a", 1, 1.0)]
    assert select_next_dispatches(q, running_user_ids=[1, 2], concurrency=2) == []


def test_empty_queue_returns_empty():
    assert select_next_dispatches([], running_user_ids=[], concurrency=2) == []


def test_single_user_fills_all_free_slots():
    # one user alone uses the whole cap, oldest first
    q = [_job("a", 1, 1.0), _job("b", 1, 2.0), _job("c", 1, 3.0)]
    assert select_next_dispatches(q, running_user_ids=[], concurrency=2) == ["a", "b"]


def test_oldest_first_within_same_load():
    q = [_job("b", 1, 2.0), _job("a", 1, 1.0)]
    assert select_next_dispatches(q, running_user_ids=[], concurrency=1) == ["a"]


def test_new_user_served_before_backlog_user():
    # user 1 dumped 30, user 2 has 1; user 1 already has 1 running, 1 free slot.
    # the free slot must go to user 2 (0 running), not user 1's backlog.
    q = [_job(f"u1-{i}", 1, float(i)) for i in range(30)] + [_job("u2", 2, 100.0)]
    assert select_next_dispatches(q, running_user_ids=[1], concurrency=2) == ["u2"]


def test_round_robin_balances_two_users():
    # nothing running, cap 2: pick one from each user, not two from the first
    q = [_job("u1-a", 1, 1.0), _job("u1-b", 1, 2.0), _job("u2-a", 2, 3.0)]
    assert select_next_dispatches(q, running_user_ids=[], concurrency=2) == ["u1-a", "u2-a"]


def test_running_load_counts_toward_fairness():
    # user 1 already has 2 running, user 2 has 0; 2 free slots, both users queued.
    # both free slots should go to user 2 (far less loaded).
    q = [_job("u1-a", 1, 1.0), _job("u2-a", 2, 2.0), _job("u2-b", 2, 3.0)]
    assert select_next_dispatches(q, running_user_ids=[1, 1], concurrency=4) == ["u2-a", "u2-b"]
