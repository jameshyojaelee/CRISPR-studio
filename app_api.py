"""Uvicorn entrypoint for the CRISPR-studio FastAPI service."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("crispr_screen_expert.api:create_app", host="0.0.0.0", port=8000, factory=True)


if __name__ == "__main__":
    main()
