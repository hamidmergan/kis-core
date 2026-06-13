from src.features.ai_assistant.scheduling.scheduler import PoolJob, select_shared_pool

W = {"studio": 2.0, "ingest": 1.0}


def _j(jid, uid, area, t):
    return PoolJob(job_id=jid, user_id=uid, area=area, created_at=t)


def test_no_free_slots():
    q = [_j("a", 1, "studio", 1.0)]
    assert select_shared_pool(q, running=[(2, "studio"), (3, "ingest")], total_slots=2, weights=W) == []


def test_empty_queue():
    assert select_shared_pool([], running=[], total_slots=2, weights=W) == []


def test_unlimited_dispatches_all_oldest_first():
    q = [_j("b", 1, "studio", 2.0), _j("a", 1, "ingest", 1.0), _j("c", 2, "studio", 3.0)]
    assert select_shared_pool(q, running=[], total_slots=0, weights=W) == ["a", "b", "c"]


def test_studio_preferred_over_ingest_by_weight():
    # both areas have demand, 2 free slots, weights studio2/ingest1
    # studio should take the larger share. With 2 slots: studio then ingest.
    q = [_j("s1", 1, "studio", 1.0), _j("s2", 2, "studio", 2.0), _j("i1", 3, "ingest", 3.0)]
    picks = select_shared_pool(q, running=[], total_slots=2, weights=W)
    assert "s1" in picks  # studio served
    assert len(picks) == 2


def test_round_robin_users_within_area():
    # one user floods studio, another has one; 2 slots both studio demand
    q = [_j("u1a", 1, "studio", 1.0), _j("u1b", 1, "studio", 2.0), _j("u2", 2, "studio", 3.0)]
    picks = select_shared_pool(q, running=[], total_slots=2, weights={"studio": 1.0})
    # fairness: one from each user, not two from user 1
    assert picks == ["u1a", "u2"]


def test_flooder_does_not_block_newcomer():
    q = [_j(f"u1-{i}", 1, "studio", float(i)) for i in range(10)] + [_j("u2", 2, "studio", 99.0)]
    # user 1 already has 1 running, 1 free slot -> newcomer u2 wins
    picks = select_shared_pool(q, running=[(1, "studio")], total_slots=2, weights={"studio": 1.0})
    assert picks == ["u2"]


def test_running_area_load_counts():
    # studio already busy (1 running), ingest idle; 1 free slot, both have demand.
    # studio is ahead of its weight share, so the free slot should go to ingest.
    q = [_j("s", 1, "studio", 1.0), _j("i", 2, "ingest", 2.0)]
    picks = select_shared_pool(q, running=[(9, "studio")], total_slots=2, weights=W)
    assert picks == ["i"]


def test_cumulative_user_fairness_interleaves_flooder_and_newcomer():
    # flooder user 1 has 6 OLD jobs, newcomer user 2 has 3 NEWER jobs. With only
    # created_at the flooder would win every tie; cumulative user_granted makes
    # them interleave 1,2,1,2,...
    ug: dict = {}
    queued = [PoolJob(f"u1-{i}", 1, "studio", float(i)) for i in range(6)] + [
        PoolJob(f"u2-{i}", 2, "studio", 100.0 + i) for i in range(3)
    ]
    order = []
    pool = list(queued)
    by_id = {j.job_id: j for j in queued}
    while pool:
        jid = select_shared_pool(pool, running=[], total_slots=1, weights={"studio": 1.0}, user_granted=ug)[0]
        order.append(by_id[jid].user_id)
        pool = [j for j in pool if j.job_id != jid]
    assert order[:6] == [1, 2, 1, 2, 1, 2]  # perfect interleave, not 1,1,1,1,1,1
