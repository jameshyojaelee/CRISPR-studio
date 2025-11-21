from __future__ import annotations

import time

import pytest

from crispr_screen_expert.background import JobManager, JobNotFoundError, JobSnapshot


def test_job_manager_completion_callback_invoked():
    manager = JobManager(max_workers=2, history_limit=10)
    seen: list[JobSnapshot] = []

    job_id = manager.submit(lambda: 42, on_complete=seen.append)
    assert manager.result(job_id) == 42
    assert len(seen) == 1
    snapshot = seen[0]
    assert snapshot.job_id == job_id
    assert snapshot.status == "finished"
    assert snapshot.started_at is not None
    assert snapshot.finished_at is not None


def test_job_manager_cleans_completed_jobs_and_preserves_recent_history():
    manager = JobManager(max_workers=8, history_limit=50)
    job_ids = [manager.submit(lambda value=value: value) for value in range(500)]

    deadline = time.time() + 10
    while True:
        statuses = [manager.status(job_id) for job_id in job_ids]
        if all(status in {"finished", "failed", "unknown"} for status in statuses):
            break
        if time.time() > deadline:
            pytest.fail("Jobs did not complete in time")
        time.sleep(0.01)

    assert len(manager.history()) == 50

    with pytest.raises(JobNotFoundError):
        manager.result(job_ids[0])

    assert manager.status(job_ids[0]) == "unknown"

    recent_job = job_ids[-1]
    assert manager.status(recent_job) == "finished"
    assert manager.result(recent_job) == 499
    metadata = manager.metadata(recent_job)
    assert metadata.started_at is not None
    assert metadata.finished_at is not None


def test_job_manager_exception_for_unknown_jobs():
    manager = JobManager()
    with pytest.raises(JobNotFoundError):
        manager.exception("missing")
    with pytest.raises(JobNotFoundError):
        manager.result("missing")
    with pytest.raises(JobNotFoundError):
        manager.metadata("missing")
