"""Dash application factory for CRISPR-studio."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import Dash

from .layout import build_layout
from .callbacks import register_callbacks


def create_app() -> Dash:
    external_stylesheets = [
        dbc.themes.CYBORG,
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap",
    ]
    app = Dash(__name__, external_stylesheets=external_stylesheets, suppress_callback_exceptions=True)
    app.title = "CRISPR-studio"
    app.layout = build_layout()
    register_callbacks(app)
    return app
