"""Lightweight analytics logger (opt-in)."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .config import get_settings


def _analytics_dir() -> Path:
    settings = get_settings()
    path = settings.logs_dir / "analytics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_event(event: str, payload: Dict[str, Any] | None = None) -> None:
    settings = get_settings()
    if not settings.enable_analytics:
        return

    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event,
    }
    if payload:
        record.update(payload)

    events_file = _analytics_dir() / "events.csv"
    write_header = not events_file.exists()

    with events_file.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted(record.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(record)


def summarise_events() -> Dict[str, Any]:
    events_file = _analytics_dir() / "events.csv"
    if not events_file.exists():
        return {"total_events": 0, "by_event": {}}

    counts: Dict[str, int] = {}
    runtimes: list[float] = []

    with events_file.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            event = row.get("event", "unknown")
            counts[event] = counts.get(event, 0) + 1
            if event == "analysis_completed" and row.get("runtime_seconds"):
                try:
                    runtimes.append(float(row["runtime_seconds"]))
                except ValueError:
                    pass

    summary: Dict[str, Any] = {
        "total_events": sum(counts.values()),
        "by_event": counts,
    }
    if runtimes:
        summary["average_runtime_seconds"] = sum(runtimes) / len(runtimes)
    return summary
