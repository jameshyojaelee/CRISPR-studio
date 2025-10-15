"""State management helpers for Dash app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class UploadedFiles:
    counts_path: Optional[Path] = None
    library_path: Optional[Path] = None
    metadata_path: Optional[Path] = None
