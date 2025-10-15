"""Simple background job manager for Dash callbacks."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional


class JobManager:
    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: Dict[str, Future[Any]] = {}
        self._lock = threading.Lock()

    def submit(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        job_id = uuid.uuid4().hex
        future = self._executor.submit(func, *args, **kwargs)
        with self._lock:
            self._jobs[job_id] = future
        return job_id

    def status(self, job_id: str) -> str:
        future = self._jobs.get(job_id)
        if future is None:
            return "unknown"
        if future.running():
            return "running"
        if future.done():
            return "finished" if future.exception() is None else "failed"
        return "queued"

    def result(self, job_id: str) -> Any:
        future = self._jobs.get(job_id)
        if future is None:
            raise KeyError(job_id)
        return future.result()

    def exception(self, job_id: str) -> Optional[BaseException]:
        future = self._jobs.get(job_id)
        if future is None:
            return None
        return future.exception()
