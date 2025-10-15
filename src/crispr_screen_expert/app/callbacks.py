"""Dash callbacks for CRISPR-studio app."""

from __future__ import annotations

import base64
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Dict

import dash
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, dcc, html
import pandas as pd
import plotly.graph_objects as go

from ..background import JobManager
from ..config import get_settings
from ..data_loader import load_counts
from ..models import AnalysisResult, load_experiment_config
from ..pipeline import DataPaths, PipelineSettings, run_analysis
from ..visualization import (
    detection_heatmap,
    pathway_enrichment_bubble,
    replicate_correlation_scatter,
    volcano_plot,
)
from . import ids

SETTINGS = get_settings()
UPLOAD_DIR = SETTINGS.uploads_dir
UPLOAD_DIR.mkdir(exist_ok=True)

JOB_MANAGER = JobManager(max_workers=2)
RESULT_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_LOCK = threading.Lock()


def _save_upload(contents: str, filename: str) -> Path:
    if not contents:
        raise ValueError("No contents to save")
    data = contents.split(",", 1)[1]
    decoded = base64.b64decode(data)
    ext = Path(filename).suffix or ".tmp"
    path = UPLOAD_DIR / f"upload_{uuid.uuid4().hex}{ext}"
    path.write_bytes(decoded)
    return path


def _config_summary(config_data: Dict[str, Any]) -> html.Div:
    if not config_data:
        return html.Div("No metadata loaded yet.")
    return dbc.Alert(
        [
            html.Div(f"Screen Type: {config_data.get('screen_type')}")
            if config_data.get("screen_type")
            else html.Div(),
            html.Div(f"Samples: {len(config_data.get('samples', []))}"),
            html.Div(f"FDR threshold: {config_data.get('analysis', {}).get('fdr_threshold')}")
            if config_data.get("analysis")
            else html.Div(),
        ],
        color="secondary",
    )


def _summary_card(title: str, value: Any) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody([html.H6(title, className="card-title"), html.H4(str(value), className="card-text")]),
        className="mb-3",
    )


def _dataset_key(*paths: Path) -> str:
    parts = []
    for path in paths:
        stat = path.stat()
        parts.append(f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}")
    return "|".join(parts)


def _run_pipeline_job(counts_path: Path, library_path: Path, metadata_path: Path) -> Dict[str, Any]:
    cache_key = _dataset_key(counts_path, library_path, metadata_path)
    with CACHE_LOCK:
        cached = RESULT_CACHE.get(cache_key)
    if cached:
        return cached

    config = load_experiment_config(metadata_path)
    result = run_analysis(
        config=config,
        paths=DataPaths(counts=counts_path, library=library_path, metadata=metadata_path),
        settings=PipelineSettings(use_mageck=False),
    )

    gene_df = pd.DataFrame([gene.model_dump() for gene in result.gene_results])
    gene_df["gene"] = gene_df.get("gene_symbol", gene_df.get("gene"))
    table_data = (
        gene_df[["gene", "score", "fdr", "log2_fold_change"]]
        .fillna({"log2_fold_change": 0, "score": 0, "fdr": 1})
        .to_dict("records")
    )

    volcano_fig = volcano_plot(gene_df)
    counts_df = load_counts(counts_path)
    detection_fig = detection_heatmap(counts_df)
    sample_columns = config.sample_columns
    if len(sample_columns) >= 2:
        replicate_fig = replicate_correlation_scatter(counts_df, sample_columns[0], sample_columns[1])
    else:
        replicate_fig = go.Figure()
        replicate_fig.update_layout(title="Insufficient replicates for correlation plot")
    pathway_fig = pathway_enrichment_bubble([pw.model_dump() for pw in result.pathway_results])

    summary_cards = dbc.Row(
        [
            dbc.Col(_summary_card("Total Guides", result.summary.total_guides)),
            dbc.Col(_summary_card("Total Genes", result.summary.total_genes)),
            dbc.Col(_summary_card("Significant Genes", result.summary.significant_genes)),
        ]
    )

    annotations = {}
    annotations_path = result.artifacts.get("gene_annotations")
    if annotations_path and Path(annotations_path).exists():
        try:
            annotations = json.loads(Path(annotations_path).read_text())
        except json.JSONDecodeError:
            annotations = {}

    payload = {
        "result": {"result": result.model_dump(mode="json"), "annotations": annotations},
        "volcano": volcano_fig,
        "replicate": replicate_fig,
        "detection": detection_fig,
        "pathways": pathway_fig,
        "summary_cards": summary_cards,
        "table_data": table_data,
    }
    with CACHE_LOCK:
        RESULT_CACHE[cache_key] = payload
    return payload


def register_callbacks(app: Dash) -> None:
    @app.callback(
        Output(ids.STORE_CONFIG, "data"),
        Output(ids.UPLOAD_STATUS, "children"),
        Output(ids.CONFIG_PANEL, "children"),
        Input(ids.UPLOAD_COUNTS, "contents"),
        Input(ids.UPLOAD_LIBRARY, "contents"),
        Input(ids.UPLOAD_METADATA, "contents"),
        State(ids.UPLOAD_COUNTS, "filename"),
        State(ids.UPLOAD_LIBRARY, "filename"),
        State(ids.UPLOAD_METADATA, "filename"),
        State(ids.STORE_CONFIG, "data"),
        prevent_initial_call=True,
    )
    def handle_uploads(
        counts_contents,
        library_contents,
        metadata_contents,
        counts_name,
        library_name,
        metadata_name,
        current_data,
    ):
        data = current_data or {}
        messages = []

        if counts_contents and counts_name:
            path = _save_upload(counts_contents, counts_name)
            data["counts_path"] = str(path)
            messages.append(f"Counts uploaded: {counts_name}")
        if library_contents and library_name:
            path = _save_upload(library_contents, library_name)
            data["library_path"] = str(path)
            messages.append(f"Library uploaded: {library_name}")
        if metadata_contents and metadata_name:
            path = _save_upload(metadata_contents, metadata_name)
            data["metadata_path"] = str(path)
            config = load_experiment_config(path)
            data["config"] = config.model_dump(mode="json")
            messages.append(f"Metadata uploaded: {metadata_name}")

        config_panel = _config_summary(data.get("config"))
        status_children = [html.Div(msg) for msg in messages] or html.Div("Awaiting uploads...")
        return data, status_children, config_panel

    @app.callback(
        Output(ids.STORE_JOB, "data"),
        Output(ids.INTERVAL_JOB, "disabled"),
        Input(ids.BUTTON_RUN_ANALYSIS, "n_clicks"),
        State(ids.STORE_CONFIG, "data"),
        prevent_initial_call=True,
    )
    def start_pipeline_job(n_clicks, config_store):
        if not config_store:
            raise dash.exceptions.PreventUpdate

        counts_path = Path(config_store.get("counts_path", ""))
        library_path = Path(config_store.get("library_path", ""))
        metadata_path = Path(config_store.get("metadata_path", ""))
        if not (counts_path.exists() and library_path.exists() and metadata_path.exists()):
            raise dash.exceptions.PreventUpdate

        job_id = JOB_MANAGER.submit(_run_pipeline_job, counts_path, library_path, metadata_path)
        return {"job_id": job_id}, False

    @app.callback(
        Output(ids.STORE_RESULTS, "data"),
        Output(ids.GRAPH_VOLCANO, "figure"),
        Output(ids.GRAPH_QC_REPLICATE, "figure"),
        Output(ids.GRAPH_QC_DETECTION, "figure"),
        Output(ids.GRAPH_PATHWAY_BUBBLE, "figure"),
        Output(ids.SUMMARY_CARDS, "children"),
        Output(ids.TABLE_GENES, "data"),
        Output(ids.STORE_JOB, "data"),
        Output(ids.INTERVAL_JOB, "disabled"),
        Input(ids.INTERVAL_JOB, "n_intervals"),
        State(ids.STORE_JOB, "data"),
        prevent_initial_call=True,
    )
    def poll_job_status(n_intervals, job_store):
        if not job_store:
            raise dash.exceptions.PreventUpdate
        job_id = job_store.get("job_id")
        status = JOB_MANAGER.status(job_id)
        if status in {"queued", "running"}:
            raise dash.exceptions.PreventUpdate

        if status == "failed":
            exception = JOB_MANAGER.exception(job_id)
            warning = f"Analysis job failed: {exception}" if exception else "Analysis job failed."
            empty_fig = go.Figure()
            summary_cards = dbc.Alert(warning, color="danger")
            return {}, empty_fig, empty_fig, empty_fig, empty_fig, summary_cards, [], None, True

        result_payload = JOB_MANAGER.result(job_id)
        return (
            result_payload["result"],
            result_payload["volcano"],
            result_payload["replicate"],
            result_payload["detection"],
            result_payload["pathways"],
            result_payload["summary_cards"],
            result_payload["table_data"],
            None,
            True,
        )

    @app.callback(
        Output(ids.GENE_MODAL, "is_open"),
        Output(ids.GENE_MODAL_BODY, "children"),
        Input(ids.TABLE_GENES, "selected_rows"),
        State(ids.TABLE_GENES, "data"),
        State(ids.GENE_MODAL, "is_open"),
        State(ids.STORE_RESULTS, "data"),
        prevent_initial_call=True,
    )
    def display_gene_modal(selected_rows, table_data, is_open, result_store):
        if not selected_rows or not table_data or not result_store:
            raise dash.exceptions.PreventUpdate
        idx = selected_rows[0]
        row = table_data[idx]
        annotations = result_store.get("annotations", {})
        analysis = AnalysisResult.model_validate(result_store.get("result"))
        gene_info = next((g for g in analysis.gene_results if g.gene_symbol == gene_symbol), None)
        gene_symbol = row.get("gene")
        annotation = annotations.get(gene_symbol, {})
        body = html.Div(
            [
                html.H4(gene_symbol),
                html.P(f"Score: {row.get('score')}") ,
                html.P(f"FDR: {row.get('fdr')}") ,
                html.P(f"log2FC: {row.get('log2_fold_change')}") ,
                html.P(f"Guides: {gene_info.n_guides if gene_info else 'N/A'}"),
                html.Hr(),
                html.P(annotation.get("summary", "No annotation available.")),
            ]
        )
        return True, body

    @app.callback(
        Output(ids.DOWNLOAD_REPORT, "data"),
        Input(ids.BUTTON_DOWNLOAD_REPORT, "n_clicks"),
        State(ids.STORE_RESULTS, "data"),
        prevent_initial_call=True,
    )
    def download_report(n_clicks, result_store):
        if not result_store:
            raise dash.exceptions.PreventUpdate

        result = AnalysisResult.model_validate(result_store.get("result"))
        from ..reporting import render_html

        html = render_html(result)
        return dict(content=html, filename="crispr_studio_report.html")
