"""Dash layout composition."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html
from dash import dash_table

from . import ids


def build_layout() -> html.Div:
    return dbc.Container(
        [
            html.H2("CRISPR-studio"),
            dcc.Store(id=ids.STORE_CONFIG),
            dcc.Store(id=ids.STORE_RESULTS),
            dcc.Store(id=ids.STORE_JOB),
            dcc.Interval(id=ids.INTERVAL_JOB, interval=4000, n_intervals=0, disabled=True),
            dcc.Tabs(
                id=ids.TABS_MAIN,
                value="upload",
                children=[
                    dcc.Tab(label="Upload", value="upload", children=_upload_tab()),
                    dcc.Tab(label="Results", value="results", children=_results_tab()),
                    dcc.Tab(label="QC", value="qc", children=_qc_tab()),
                    dcc.Tab(label="Pathways", value="pathways", children=_pathways_tab()),
                    dcc.Tab(label="Reports", value="reports", children=_reports_tab()),
                ],
            ),
        ],
        fluid=True,
        className="py-4",
    )


def _upload_tab() -> html.Div:
    return dbc.Row(
        [
            dbc.Col(
                [
                    html.H4("Upload Data"),
                    dcc.Upload(id=ids.UPLOAD_COUNTS, children=html.Div(["Drag and drop counts file"]), multiple=False),
                    dcc.Upload(id=ids.UPLOAD_LIBRARY, children=html.Div(["Drag and drop library file"]), multiple=False),
                    dcc.Upload(id=ids.UPLOAD_METADATA, children=html.Div(["Drag and drop metadata file"]), multiple=False),
                    html.Div(id=ids.UPLOAD_STATUS, className="mt-3"),
                    dbc.Button("Run Analysis", id=ids.BUTTON_RUN_ANALYSIS, color="primary", className="mt-3"),
                ],
                md=6,
            ),
            dbc.Col([html.H4("Configuration"), html.Div(id=ids.CONFIG_PANEL)], md=6),
        ]
    )


def _results_tab() -> html.Div:
    return html.Div(
        [
            html.Div(id=ids.SUMMARY_CARDS, className="mb-4"),
            dcc.Graph(id=ids.GRAPH_VOLCANO),
            dash_table.DataTable(
                id=ids.TABLE_GENES,
                columns=[
                    {"name": "Gene", "id": "gene"},
                    {"name": "Score", "id": "score"},
                    {"name": "FDR", "id": "fdr"},
                    {"name": "log2FC", "id": "log2_fold_change"},
                ],
                data=[],
                sort_action="native",
                filter_action="native",
                row_selectable="single",
                page_size=10,
                style_table={"overflowX": "auto"},
            ),
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Gene Details")),
                    dbc.ModalBody(id=ids.GENE_MODAL_BODY),
                ],
                id=ids.GENE_MODAL,
                size="lg",
            ),
        ]
    )


def _qc_tab() -> html.Div:
    return html.Div(
        [
            dcc.Graph(id=ids.GRAPH_QC_REPLICATE),
            dcc.Graph(id=ids.GRAPH_QC_DETECTION),
        ]
    )


def _pathways_tab() -> html.Div:
    return html.Div([dcc.Graph(id=ids.GRAPH_PATHWAY_BUBBLE)])


def _reports_tab() -> html.Div:
    return html.Div(
        [
            dbc.Button("Download HTML Report", id=ids.BUTTON_DOWNLOAD_REPORT, color="secondary"),
            dcc.Download(id=ids.DOWNLOAD_REPORT),
        ]
    )
