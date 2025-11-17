"""Dash layout composition."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html
from dash.development.base_component import Component

from . import ids
from .constants import DEFAULT_PIPELINE_SETTINGS, ENRICHR_LIBRARY_OPTIONS


def build_layout() -> Component:
    """Compose the full Dash layout with hero banner and tabbed content."""
    return html.Div(
        [
            dcc.Store(id=ids.STORE_CONFIG),
            dcc.Store(id=ids.STORE_RESULTS),
            dcc.Store(id=ids.STORE_JOB),
            dcc.Store(id=ids.STORE_SELECTED_GENE),
            dcc.Store(id=ids.STORE_HISTORY),
            dcc.Store(id=ids.STORE_PIPELINE_SETTINGS, data=DEFAULT_PIPELINE_SETTINGS),
            dcc.Interval(id=ids.INTERVAL_JOB, interval=2000, n_intervals=0, disabled=True),
            dcc.Interval(id=ids.INTERVAL_HISTORY, interval=20000, n_intervals=0, disabled=False),
            dcc.Download(id=ids.DOWNLOAD_GENE),
            _build_hero(),
            dbc.Container(
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Tabs(
                                id=ids.TABS_MAIN,
                                active_tab="upload",
                                className="main-tabs",
                                children=[
                                    dbc.Tab(_upload_tab(), label="Data Uploader", tab_id="upload"),
                                    dbc.Tab(_results_tab(), label="Results Explorer", tab_id="results"),
                                    dbc.Tab(_qc_tab(), label="Quality Control", tab_id="qc"),
                                    dbc.Tab(_pathways_tab(), label="Pathway Insights", tab_id="pathways"),
                                    dbc.Tab(_reports_tab(), label="Reporting Studio", tab_id="reports"),
                                ],
                            ),
                            lg=9,
                            xl=9,
                        ),
                        dbc.Col(_history_sidebar(), lg=3, xl=3, className="history-sidebar"),
                    ],
                    className="g-4 main-content-row",
                ),
                fluid=True,
                className="content-container",
            ),
            _job_status_overlay(),
        ],
        className="app-root",
    )


def _build_hero() -> Component:
    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    html.Span("CRISPR Studio", className="hero-eyebrow"),
                                    html.H1("High-fidelity CRISPR screen intelligence"),
                                    html.P(
                                        "Upload screens, surface hits, and narrate pathways with an immersive "
                                        "dark-mode experience tailored for wet-lab and computational teams."
                                    ),
                                    dbc.Button(
                                        "Start New Analysis",
                                        id="hero-run-analysis",
                                        color="primary",
                                        className="hero-cta",
                                        href="#",
                                    ),
                                ],
                                className="hero-copy glass-card",
                            )
                        ],
                        md=7,
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                html.Div(className="hero-accent"),
                                html.Ul(
                                    [
                                        html.Li(html.Span("⚡ Native-accelerated RRA & enrichment")),
                                        html.Li(html.Span("📊 Professional dashboards & QC visuals")),
                                        html.Li(html.Span("🧬 Pathway context and gene annotations")),
                                    ],
                                    className="hero-highlight-list",
                                ),
                            ],
                            className="hero-embellishment glass-card",
                        ),
                        md=5,
                    ),
                ],
                align="center",
                className="g-4",
            )
        ],
        fluid=True,
        className="hero-container",
    )


def _upload_tab() -> Component:
    return dbc.Row(
        [
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H4("Upload Dataset", className="section-title"),
                            html.P(
                                "Drop your counts matrix, library annotation, and metadata files. "
                                "We automatically validate structures before launching the pipeline.",
                                className="section-subtitle",
                            ),
                            _upload_zone(ids.UPLOAD_COUNTS, "Counts matrix (.csv / .tsv)"),
                            _upload_zone(ids.UPLOAD_LIBRARY, "Library annotation (.csv / .tsv)"),
                            _upload_zone(ids.UPLOAD_METADATA, "Metadata (.json)"),
                            html.Div(id=ids.UPLOAD_STATUS, className="mt-3 upload-status"),
                            _pipeline_settings_panel(),
                            dbc.Button(
                                "Run Analysis",
                                id=ids.BUTTON_RUN_ANALYSIS,
                                color="primary",
                                className="mt-4 run-analysis-btn",
                            ),
                        ]
                    ),
                    className="glass-card h-100",
                ),
                lg=7,
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H4("Configuration Preview", className="section-title"),
                            html.P(
                                "Review experiment metadata and inferred parameters before processing.",
                                className="section-subtitle",
                            ),
                            html.Div(id=ids.CONFIG_PANEL, className="config-panel"),
                        ]
                    ),
                    className="glass-card h-100",
                ),
                lg=5,
            ),
        ],
        className="g-4 upload-layout",
    )


def _results_tab() -> Component:
    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H4("Key Metrics", className="section-title"),
                                    html.Div(id=ids.SUMMARY_CARDS, className="summary-cards d-flex gap-3 flex-wrap"),
                                ]
                            ),
                            className="glass-card",
                        ),
                        lg=12,
                    )
                ],
                className="g-4",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H4("Volcano Plot", className="section-title"),
                                    dcc.Graph(id=ids.GRAPH_VOLCANO, className="graph-card"),
                                ]
                            ),
                            className="glass-card h-100",
                        ),
                        lg=6,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H4("Gene Leaderboard", className="section-title"),
                                    dash_table.DataTable(  # type: ignore[attr-defined]
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
                                        page_size=12,
                                        style_as_list_view=True,
                                        style_header={
                                            "backgroundColor": "rgba(255,255,255,0.05)",
                                            "fontWeight": "600",
                                            "border": "0",
                                        },
                                        style_data={
                                            "backgroundColor": "rgba(255,255,255,0.02)",
                                            "border": "0",
                                            "color": "var(--neutral-100)",
                                        },
                                        style_table={"overflowX": "auto"},
                                    ),
                                ]
                            ),
                            className="glass-card h-100",
                        ),
                        lg=6,
                    ),
                ],
                className="g-4 mt-1",
            ),
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Gene Details"), className="modal-header-accent"),
                    dbc.ModalBody(id=ids.GENE_MODAL_BODY, className="modal-body-dark"),
                ],
                id=ids.GENE_MODAL,
                size="lg",
                className="gene-modal",
            ),
        ],
        fluid=True,
        className="results-container",
    )


def _qc_tab() -> Component:
    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H4("Replicate Correlation", className="section-title"),
                                    dcc.Graph(id=ids.GRAPH_QC_REPLICATE, className="graph-card"),
                                ]
                            ),
                            className="glass-card h-100",
                        ),
                        lg=6,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H4("Guide Detection", className="section-title"),
                                    dcc.Graph(id=ids.GRAPH_QC_DETECTION, className="graph-card"),
                                ]
                            ),
                            className="glass-card h-100",
                        ),
                        lg=6,
                    ),
                ],
                className="g-4",
            )
        ],
        fluid=True,
        className="qc-container",
    )


def _pathways_tab() -> Component:
    return dbc.Container(
        [
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H4("Pathway Enrichment", className="section-title"),
                                dcc.Graph(id=ids.GRAPH_PATHWAY_BUBBLE, className="graph-card"),
                            ]
                        ),
                        className="glass-card",
                    ),
                    lg=12,
                ),
                className="g-4",
            )
        ],
        fluid=True,
        className="pathways-container",
    )


def _reports_tab() -> Component:
    return dbc.Container(
        [
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H4("Reporting Studio", className="section-title"),
                                html.P(
                                    "Download rich HTML reports with interactive summaries, or integrate the "
                                    "JSON artifacts into your automation workflows.",
                                    className="section-subtitle",
                                ),
                                dbc.Button(
                                    "Download HTML Report",
                                    id=ids.BUTTON_DOWNLOAD_REPORT,
                                    color="primary",
                                    className="mt-3",
                                ),
                                dbc.Button(
                                    "Download Sample Bundle",
                                    id=ids.BUTTON_DOWNLOAD_SAMPLE_REPORT,
                                    color="secondary",
                                    outline=True,
                                    className="mt-3 ms-2",
                                    disabled=True,
                                ),
                                dcc.Download(id=ids.DOWNLOAD_REPORT),
                                dcc.Download(id=ids.DOWNLOAD_SAMPLE_REPORT),
                                html.Small(
                                    "Run `make build-report` to refresh the latest analysis and regenerate the showcase bundle.",
                                    className="muted mt-3 d-block",
                                ),
                            ]
                        ),
                        className="glass-card",
                    ),
                    lg=6,
                ),
                className="justify-content-center",
            )
        ],
        fluid=True,
        className="reports-container",
    )


def _upload_zone(component_id: str, label: str) -> Component:
    return dcc.Upload(
        id=component_id,
        multiple=False,
        children=html.Div(
            [
                html.Div(className="upload-icon"),
                html.Div(
                    [
                        html.Span(label, className="upload-label"),
                        html.Small("Drag & drop or click to browse", className="upload-hint"),
                    ],
                    className="upload-text",
                ),
            ],
            className="upload-inner",
        ),
        className="upload-dropzone",
    )


def _pipeline_settings_panel() -> Component:
    return html.Div(
        [
            html.Div(
                [
                    html.Div("Execution backends", className="pipeline-settings-label"),
                    html.Div(
                        [
                            _pipeline_switch(ids.SWITCH_USE_MAGECK, "Enable MAGeCK scoring", DEFAULT_PIPELINE_SETTINGS["use_mageck"]),
                            _pipeline_switch(ids.SWITCH_NATIVE_RRA, "Use native RRA backend", DEFAULT_PIPELINE_SETTINGS["use_native_rra"]),
                            _pipeline_switch(ids.SWITCH_NATIVE_ENRICHMENT, "Use native enrichment backend", DEFAULT_PIPELINE_SETTINGS["use_native_enrichment"]),
                        ],
                        className="pipeline-switch-grid",
                    ),
                ],
                className="pipeline-settings-block",
            ),
            html.Div(
                [
                    html.Div("Enrichr libraries", className="pipeline-settings-label"),
                    dcc.Dropdown(
                        id=ids.DROPDOWN_ENRICHR,
                        options=ENRICHR_LIBRARY_OPTIONS,
                        multi=True,
                        placeholder="Select optional libraries…",
                        value=DEFAULT_PIPELINE_SETTINGS["enrichr_libraries"],
                        className="pipeline-dropdown",
                        persistence=True,
                        persistence_type="session",
                    ),
                    html.Small(
                        "Leave empty to skip enrichment or supply the native library name when using the accelerated backend.",
                        className="pipeline-settings-hint",
                    ),
                ],
                className="pipeline-settings-block",
            ),
            html.Div(
                [
                    _pipeline_switch(
                        ids.SWITCH_SKIP_ANNOTATIONS,
                        "Skip gene annotations (offline mode)",
                        DEFAULT_PIPELINE_SETTINGS["skip_annotations"],
                    ),
                ],
                className="pipeline-settings-block",
            ),
        ],
        className="pipeline-settings-panel mt-4",
    )


def _pipeline_switch(component_id: str, label: str, value: bool) -> Component:
    return dbc.Switch(
        id=component_id,
        label=label,
        value=value,
        className="pipeline-switch",
        persistence=True,
        persistence_type="session",
    )


def _history_sidebar() -> Component:
    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    [
                        html.H4("Run History", className="history-title", id=ids.RUN_HISTORY_TITLE),
                        html.Small("Last five completed analyses", className="history-subtitle"),
                    ],
                    className="d-flex flex-column gap-1 mb-3",
                ),
                html.Div(id=ids.RUN_HISTORY_CONTAINER, className="history-list"),
                html.Div(
                    "No completed runs yet.",
                    id=ids.RUN_HISTORY_EMPTY,
                    className="history-empty",
                    hidden=True,
                ),
            ]
        ),
        className="glass-card history-card",
    )


def _job_status_overlay() -> Component:
    return html.Div(
        [
            dbc.Card(
                [
                    dbc.CardBody(
                        [
                            dbc.Spinner(color="light", size="sm", className="me-2"),
                            html.Div(
                                [
                                    html.Div(id=ids.JOB_STATUS_TEXT, className="job-status-title"),
                                    html.Small(id=ids.JOB_STATUS_RUNTIME, className="job-status-runtime"),
                                ],
                                className="flex-grow-1",
                            ),
                            dbc.Button(
                                "Dismiss",
                                id=ids.JOB_STATUS_DISMISS,
                                color="link",
                                className="job-status-dismiss",
                            ),
                        ],
                        className="d-flex align-items-center gap-3",
                    ),
                    html.Div(
                        [
                            html.Small("Active settings", className="job-status-settings-label"),
                            html.Div(id=ids.JOB_STATUS_SETTINGS, className="job-status-settings"),
                        ],
                        className="job-status-settings-block",
                    ),
                    html.Div(id=ids.JOB_STATUS_WARNINGS, className="job-status-warnings"),
                ],
                className="job-status-card glass-card",
            )
        ],
        id=ids.JOB_STATUS_OVERLAY,
        className="job-status-overlay hidden",
    )
