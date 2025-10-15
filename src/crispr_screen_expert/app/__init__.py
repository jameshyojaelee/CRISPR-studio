"""Dash application factory for CRISPR-studio."""

from __future__ import annotations

from dash import Dash
import dash_bootstrap_components as dbc

from .layout import build_layout
from .callbacks import register_callbacks


def create_app() -> Dash:
    app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])
    app.title = "CRISPR-studio"
    app.layout = build_layout()
    register_callbacks(app)
    return app
