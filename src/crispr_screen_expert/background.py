"""Simple background job manager for Dash callbacks."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass
class JobSnapshot:
    """Public snapshot of job lifecycle information."""

    job_id: str
    status: str
    submitted_at: float
    started_at: Optional[float]
    finished_at: Optional[float]
    exception: Optional[str] = None


@dataclass
class _JobRecord:
    job_id: str
    submitted_at: float
    status: str = "queued"
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    result: Any = None
    exception: Optional[BaseException] = None

    def snapshot(self) -> JobSnapshot:
        return JobSnapshot(
            job_id=self.job_id,
            status=self.status,
            submitted_at=self.submitted_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            exception=str(self.exception) if self.exception else None,
        )


class JobNotFoundError(KeyError):
    """Raised when a job cannot be located in the manager history."""

    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job '{job_id}' not found")
        self.job_id = job_id


class JobManager:
    def __init__(
        self,
        max_workers: int = 2,
        *,
        history_limit: int = 50,
        completion_callbacks: Optional[Sequence[Callable[[JobSnapshot], None]]] = None,
    ) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: Dict[str, Future[Any]] = {}
        self._records: Dict[str, _JobRecord] = {}
        self._history: Deque[str] = deque()
        self._history_limit = history_limit
        self._completion_callbacks: List[Callable[[JobSnapshot], None]] = list(completion_callbacks or [])
        self._lock = threading.Lock()

    def submit(
        self,
        func: Callable[..., Any],
        *args: Any,
        on_complete: Optional[Callable[[JobSnapshot], None]] = None,
        **kwargs: Any,
    ) -> str:
        job_id = uuid.uuid4().hex
        record = _JobRecord(job_id=job_id, submitted_at=time.time())

        def _wrapped() -> Any:
            with self._lock:
                record.started_at = time.time()
                record.status = "running"
            try:
                result = func(*args, **kwargs)
                with self._lock:
                    record.result = result
                    record.status = "finished"
                return result
            except BaseException as exc:  # pragma: no cover - defensive
                with self._lock:
                    record.exception = exc
                    record.status = "failed"
                raise
            finally:
                with self._lock:
                    record.finished_at = time.time()

        future = self._executor.submit(_wrapped)
        with self._lock:
            self._jobs[job_id] = future
            self._records[job_id] = record
        future.add_done_callback(lambda _f: self._finalise(job_id, on_complete))
        return job_id

    def _finalise(self, job_id: str, job_callback: Optional[Callable[[JobSnapshot], None]]) -> None:
        callbacks: List[Callable[[JobSnapshot], None]] = []
        snapshot: Optional[JobSnapshot] = None
        with self._lock:
            self._jobs.pop(job_id, None)
            record = self._records.get(job_id)
            if record is None:
                return
            if record.finished_at is None:
                record.finished_at = time.time()
            snapshot = record.snapshot()
            self._history.append(job_id)
            while len(self._history) > self._history_limit:
                oldest = self._history.popleft()
                if oldest not in self._jobs:
                    self._records.pop(oldest, None)
            callbacks.extend(self._completion_callbacks)
            if job_callback:
                callbacks.append(job_callback)

        if snapshot is None:
            return

        for callback in callbacks:
            try:
                callback(snapshot)
            except Exception:  # pragma: no cover - callbacks should not break the pool
                logger.exception("Job completion callback failed for %s", job_id)

    def status(self, job_id: str) -> str:
        with self._lock:
            record = self._records.get(job_id)
            if record is None:
                return "unknown"
            return record.status

    def metadata(self, job_id: str) -> JobSnapshot:
        with self._lock:
            record = self._records.get(job_id)
            if record is None:
                raise JobNotFoundError(job_id)
            return record.snapshot()

    def history(self) -> List[JobSnapshot]:
        with self._lock:
            snapshots: List[JobSnapshot] = []
            for job_id in list(self._history):
                record = self._records.get(job_id)
                if record is not None:
                    snapshots.append(record.snapshot())
            return snapshots

    def result(self, job_id: str) -> Any:
        with self._lock:
            future = self._jobs.get(job_id)
            record = self._records.get(job_id)
        if record is None:
            raise JobNotFoundError(job_id)
        if future is not None:
            return future.result()
        if record.exception is not None:
            raise record.exception
        return record.result

    def exception(self, job_id: str) -> Optional[BaseException]:
        with self._lock:
            future = self._jobs.get(job_id)
            record = self._records.get(job_id)
        if record is None:
            raise JobNotFoundError(job_id)
        if future is not None:
            return future.exception()
        return record.exception
