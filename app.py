"""WSGI entrypoint for Dash app."""

from __future__ import annotations

from crispr_screen_expert.app import create_app

app = create_app()
server = app.server


if __name__ == "__main__":
    app.run(debug=True)
