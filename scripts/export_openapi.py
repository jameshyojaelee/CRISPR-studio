"""Export the FastAPI OpenAPI schema to artifacts/api_schema.json."""

from __future__ import annotations

import json
from pathlib import Path

from crispr_screen_expert.api import create_app
from crispr_screen_expert.config import get_settings


def export_schema() -> Path:
    settings = get_settings()
    app = create_app()
    schema = app.openapi()
    output_path = settings.artifacts_dir / "api_schema.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(schema, indent=2))
    return output_path


if __name__ == "__main__":
    path = export_schema()
    print(f"OpenAPI schema written to {path}")
