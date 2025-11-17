"""Dash callbacks for CRISPR-studio app."""

from __future__ import annotations

import base64
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import time
import hashlib

import dash
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, dcc, html, no_update, callback_context
from dash.dependencies import ALL
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
from .constants import DEFAULT_PIPELINE_SETTINGS

SETTINGS = get_settings()
UPLOAD_DIR = SETTINGS.uploads_dir
UPLOAD_DIR.mkdir(exist_ok=True)

JOB_MANAGER = JobManager(max_workers=2)
RESULT_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_LOCK = threading.Lock()


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _normalise_settings_data(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    settings = dict(DEFAULT_PIPELINE_SETTINGS)
    if not data:
        return settings

    settings["use_mageck"] = _coerce_bool(data.get("use_mageck"), settings["use_mageck"])
    settings["use_native_rra"] = _coerce_bool(data.get("use_native_rra"), settings["use_native_rra"])
    settings["use_native_enrichment"] = _coerce_bool(
        data.get("use_native_enrichment"),
        settings["use_native_enrichment"],
    )
    libraries = data.get("enrichr_libraries") or []
    if isinstance(libraries, str):
        libraries = [item.strip() for item in libraries.split(",") if item.strip()]
    else:
        libraries = [str(item) for item in libraries if item]
    settings["enrichr_libraries"] = libraries

    if "skip_annotations" in data:
        settings["skip_annotations"] = _coerce_bool(data["skip_annotations"], settings["skip_annotations"])
    elif "cache_annotations" in data:
        cache_annotations = _coerce_bool(data["cache_annotations"], True)
        settings["skip_annotations"] = not cache_annotations

    return settings


def _settings_fingerprint(settings: Dict[str, Any]) -> str:
    payload = json.dumps(settings, sort_keys=True).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def _settings_snapshot(actual: PipelineSettings, requested: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = {
        "use_mageck": actual.use_mageck,
        "use_native_rra": actual.use_native_rra,
        "use_native_enrichment": actual.use_native_enrichment,
        "enrichr_libraries": list(actual.enrichr_libraries or []),
        "skip_annotations": not actual.cache_annotations,
    }
    if not snapshot["enrichr_libraries"] and requested.get("enrichr_libraries"):
        snapshot["enrichr_libraries"] = list(requested["enrichr_libraries"])
    return snapshot


def _settings_badges(settings: Optional[Dict[str, Any]]) -> html.Div:
    payload = settings or DEFAULT_PIPELINE_SETTINGS
    libraries = payload.get("enrichr_libraries") or []

    badges = [
        dbc.Badge(
            "MAGeCK" if payload.get("use_mageck") else "RRA only",
            className="job-settings-badge",
        ),
        dbc.Badge(
            "Native RRA" if payload.get("use_native_rra") else "Python RRA",
            className="job-settings-badge",
        ),
        dbc.Badge(
            "Native enrichment"
            if payload.get("use_native_enrichment")
            else ("Enrichr" if libraries else "Enrichment off"),
            className="job-settings-badge",
        ),
        dbc.Badge(
            "Skip annotations" if payload.get("skip_annotations") else "Annotations on",
            className="job-settings-badge",
        ),
    ]
    if libraries:
        preview = ", ".join(libraries[:2])
        if len(libraries) > 2:
            preview += "…"
        badges.append(
            dbc.Badge(f"Libraries: {preview}", className="job-settings-badge subtle"),
        )
    return html.Div(badges, className="job-settings-pill-row")


def _load_run_settings(run_dir: Path) -> Optional[Dict[str, Any]]:
    settings_path = run_dir / "pipeline_settings.json"
    if not settings_path.exists():
        return None
    try:
        payload = json.loads(settings_path.read_text())
    except Exception:
        return None
    return _normalise_settings_data(payload)


def _build_pipeline_settings(settings_data: Dict[str, Any]) -> PipelineSettings:
    libraries = list(settings_data.get("enrichr_libraries") or [])
    return PipelineSettings(
        use_mageck=settings_data.get("use_mageck", True),
        use_native_rra=settings_data.get("use_native_rra", False),
        use_native_enrichment=settings_data.get("use_native_enrichment", False),
        enrichr_libraries=libraries or None,
        cache_annotations=not settings_data.get("skip_annotations", False),
    )


def _format_timestamp(run_name: str) -> str:
    try:
        dt = datetime.strptime(run_name, "%Y%m%d_%H%M%S")
        return dt.strftime("%b %d, %Y %H:%M")
    except ValueError:
        return run_name


def _summary_cards_row(result: AnalysisResult) -> dbc.Row:
    return dbc.Row(
        [
            dbc.Col(_summary_card("Total Guides", result.summary.total_guides)),
            dbc.Col(_summary_card("Total Genes", result.summary.total_genes)),
            dbc.Col(_summary_card("Significant Genes", result.summary.significant_genes)),
        ]
    )


def _load_counts_frame(counts_path: Path) -> pd.DataFrame | None:
    if not counts_path or not counts_path.exists():
        return None
    try:
        return load_counts(counts_path)
    except Exception:
        try:
            df = pd.read_csv(counts_path)
            if "guide_id" in df.columns:
                df = df.set_index("guide_id")
            return df
        except Exception:
            return None


def _build_dash_payload(result: AnalysisResult, counts_source: Path) -> Dict[str, Any]:
    gene_df = pd.DataFrame([gene.model_dump() for gene in result.gene_results])
    if not gene_df.empty:
        gene_df["gene"] = gene_df.get("gene_symbol", gene_df.get("gene"))
    else:
        gene_df = pd.DataFrame(columns=["gene", "score", "fdr", "log2_fold_change"])

    table_data = (
        gene_df[["gene", "score", "fdr", "log2_fold_change"]]
        .fillna({"log2_fold_change": 0, "score": 0, "fdr": 1})
        .to_dict("records")
    )

    if gene_df.empty:
        volcano_fig = go.Figure()
        volcano_fig.update_layout(title="No gene results available yet.")
    else:
        volcano_fig = volcano_plot(gene_df)

    counts_df = _load_counts_frame(counts_source)
    if counts_df is None or counts_df.empty:
        replicate_fig = go.Figure()
        replicate_fig.update_layout(title="Counts unavailable for replicate correlation")
        detection_fig = go.Figure()
        detection_fig.update_layout(title="Counts unavailable for detection heatmap")
    else:
        sample_columns = [sample.file_column for sample in result.config.samples]
        if len(sample_columns) >= 2:
            replicate_fig = replicate_correlation_scatter(counts_df, sample_columns[0], sample_columns[1])
        else:
            replicate_fig = go.Figure()
            replicate_fig.update_layout(title="Insufficient replicates for correlation plot")
        detection_fig = detection_heatmap(counts_df)

    pathway_fig = pathway_enrichment_bubble([pw.model_dump() for pw in result.pathway_results])

    summary_cards = _summary_cards_row(result)

    annotations = {}
    annotations_path = result.artifacts.get("gene_annotations")
    if annotations_path and Path(annotations_path).exists():
        try:
            annotations = json.loads(Path(annotations_path).read_text())
        except json.JSONDecodeError:
            annotations = {}

    analysis_result_path = result.artifacts.get("analysis_result")
    run_dir = Path(analysis_result_path).parent if analysis_result_path else None

    payload: Dict[str, Any] = {
        "result": {"result": result.model_dump(mode="json"), "annotations": annotations},
        "volcano": volcano_fig,
        "replicate": replicate_fig,
        "detection": detection_fig,
        "pathways": pathway_fig,
        "summary_cards": summary_cards,
        "table_data": table_data,
        "warnings": [warning.model_dump(mode="json") for warning in result.warnings],
        "runtime_seconds": result.summary.runtime_seconds,
        "run_dir": str(run_dir) if run_dir else None,
        "run_label": _format_timestamp(run_dir.name) if isinstance(run_dir, Path) else None,
    }
    return payload


def _list_recent_runs(limit: int = 5) -> List[Dict[str, Any]]:
    root = SETTINGS.artifacts_dir
    runs: List[Dict[str, Any]] = []
    if not root.exists():
        return runs

    directories = sorted([path for path in root.iterdir() if path.is_dir()], reverse=True)
    for run_dir in directories:
        result_path = run_dir / "analysis_result.json"
        if not result_path.exists():
            continue
        try:
            data = json.loads(result_path.read_text())
        except json.JSONDecodeError:
            continue
        summary = data.get("summary", {}) or {}
        config = data.get("config", {}) or {}
        run_info = {
            "id": run_dir.name,
            "path": str(run_dir),
            "result_path": str(result_path),
            "summary": summary,
            "config": config,
            "warnings": data.get("warnings", []),
            "label": f"{config.get('experiment_name', 'Untitled')} — {_format_timestamp(run_dir.name)}",
        }
        settings = _load_run_settings(run_dir)
        if settings:
            run_info["settings"] = settings
        runs.append(run_info)
        if len(runs) >= limit:
            break
    return runs


def _build_history_item(run: Dict[str, Any]) -> dbc.ListGroupItem:
    hits = run["summary"].get("significant_genes")
    runtime = run["summary"].get("runtime_seconds")
    subtitle_parts = []
    if hits is not None:
        subtitle_parts.append(f"{hits} significant hits")
    if runtime is not None:
        subtitle_parts.append(f"{runtime:.1f}s runtime")
    if not subtitle_parts:
        subtitle_parts.append("No summary metrics available")

    warning_badge = (
        dbc.Badge("Warnings", color="warning", className="history-item-warning-badge")
        if run.get("warnings")
        else None
    )

    settings_markup = _settings_badges(run.get("settings"))

    return dbc.ListGroupItem(
        [
            html.Div(run["label"], className="history-item-title"),
            html.Small(" • ".join(subtitle_parts), className="history-item-subtitle"),
            settings_markup,
            warning_badge,
        ],
        action=True,
        id={"type": ids.RUN_HISTORY_ITEM, "run_id": run["id"]},
        className="history-item",
    )


def _load_run_payload(run_dir: Path) -> Dict[str, Any]:
    result_path = run_dir / "analysis_result.json"
    data = json.loads(result_path.read_text())
    result = AnalysisResult.model_validate(data)
    raw_counts = Path(result.artifacts.get("raw_counts", ""))
    counts_source = raw_counts if raw_counts.exists() else Path(result.artifacts.get("normalized_counts", ""))
    payload = _build_dash_payload(result, counts_source)
    payload["run_dir"] = str(run_dir)
    payload["run_label"] = f"{result.config.experiment_name or 'Untitled'} — {_format_timestamp(run_dir.name)}"
    return payload


def _payload_to_outputs(payload: Dict[str, Any]):
    return (
        payload["result"],
        payload["volcano"],
        payload["replicate"],
        payload["detection"],
        payload["pathways"],
        payload["summary_cards"],
        payload["table_data"],
    )


def _error_outputs(message: str):
    empty_fig = go.Figure()
    summary_cards = dbc.Alert(message, color="danger")
    return (
        {},
        empty_fig,
        empty_fig,
        empty_fig,
        empty_fig,
        summary_cards,
        [],
    )


def _warning_text(warning: Any) -> str:
    if hasattr(warning, "message"):
        code = getattr(warning, "code", "")
        prefix = f"[{code}] " if code else ""
        return f"{prefix}{getattr(warning, 'message')}"
    if isinstance(warning, dict):
        code = warning.get("code")
        message = warning.get("message") or warning.get("text") or ""
        prefix = f"[{code}] " if code else ""
        return f"{prefix}{message}"
    return str(warning)


def _warnings_markup(warnings: List[Any]) -> List[html.Div]:
    if not warnings:
        return []
    return [
        dbc.Alert(_warning_text(warning), color="warning", className="mb-2 job-warning-alert")
        for warning in warnings
    ]


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


def _dataset_key(*paths: Path, settings_fingerprint: Optional[str] = None) -> str:
    parts = []
    for path in paths:
        stat = path.stat()
        parts.append(f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}")
    if settings_fingerprint:
        parts.append(settings_fingerprint)
    return "|".join(parts)


def _run_pipeline_job(
    counts_path: Path,
    library_path: Path,
    metadata_path: Path,
    settings_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized_settings = _normalise_settings_data(settings_payload)
    fingerprint = _settings_fingerprint(normalized_settings)
    cache_key = _dataset_key(counts_path, library_path, metadata_path, settings_fingerprint=fingerprint)
    with CACHE_LOCK:
        cached = RESULT_CACHE.get(cache_key)
    if cached:
        return cached

    config = load_experiment_config(metadata_path)
    pipeline_settings = _build_pipeline_settings(normalized_settings)
    result = run_analysis(
        config=config,
        paths=DataPaths(counts=counts_path, library=library_path, metadata=metadata_path),
        settings=pipeline_settings,
    )
    raw_counts = Path(result.artifacts.get("raw_counts", ""))
    counts_source = raw_counts if raw_counts.exists() else counts_path
    payload = _build_dash_payload(result, counts_source)
    snapshot = _settings_snapshot(pipeline_settings, normalized_settings)
    payload["settings"] = snapshot
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
        Output(ids.STORE_PIPELINE_SETTINGS, "data"),
        Input(ids.SWITCH_USE_MAGECK, "value"),
        Input(ids.SWITCH_NATIVE_RRA, "value"),
        Input(ids.SWITCH_NATIVE_ENRICHMENT, "value"),
        Input(ids.SWITCH_SKIP_ANNOTATIONS, "value"),
        Input(ids.DROPDOWN_ENRICHR, "value"),
        State(ids.STORE_PIPELINE_SETTINGS, "data"),
    )
    def sync_pipeline_settings(use_mageck, native_rra, native_enrichment, skip_annotations, libraries, current_store):
        store = _normalise_settings_data(current_store)
        store["use_mageck"] = bool(use_mageck)
        store["use_native_rra"] = bool(native_rra)
        store["use_native_enrichment"] = bool(native_enrichment)
        store["skip_annotations"] = bool(skip_annotations)
        library_values = libraries or []
        store["enrichr_libraries"] = [value for value in library_values if value]
        return store

    @app.callback(
        Output(ids.STORE_JOB, "data"),
        Output(ids.INTERVAL_JOB, "disabled"),
        Input(ids.BUTTON_RUN_ANALYSIS, "n_clicks"),
        State(ids.STORE_CONFIG, "data"),
        State(ids.STORE_PIPELINE_SETTINGS, "data"),
        prevent_initial_call=True,
    )
    def start_pipeline_job(n_clicks, config_store, settings_store):
        if not config_store:
            raise dash.exceptions.PreventUpdate

        counts_path = Path(config_store.get("counts_path", ""))
        library_path = Path(config_store.get("library_path", ""))
        metadata_path = Path(config_store.get("metadata_path", ""))
        if not (counts_path.exists() and library_path.exists() and metadata_path.exists()):
            raise dash.exceptions.PreventUpdate

        settings_data = _normalise_settings_data(settings_store)
        job_id = JOB_MANAGER.submit(
            _run_pipeline_job,
            counts_path,
            library_path,
            metadata_path,
            settings_data,
        )
        job_data = {
            "job_id": job_id,
            "status": "queued",
            "submitted": time.time(),
            "settings": settings_data,
        }
        return job_data, False

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
        Output(ids.JOB_STATUS_TEXT, "children"),
        Output(ids.JOB_STATUS_RUNTIME, "children"),
        Output(ids.JOB_STATUS_WARNINGS, "children"),
        Output(ids.JOB_STATUS_SETTINGS, "children"),
        Output(ids.JOB_STATUS_OVERLAY, "className"),
        Input(ids.INTERVAL_JOB, "n_intervals"),
        Input(ids.JOB_STATUS_DISMISS, "n_clicks"),
        State(ids.STORE_JOB, "data"),
        prevent_initial_call=True,
    )
    def poll_job_status(_n_intervals, dismiss_clicks, job_store):
        triggered = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else None

        default_graph_outputs = (no_update, no_update, no_update, no_update, no_update, no_update, no_update)
        overlay_hidden = "job-status-overlay hidden"

        if triggered == ids.JOB_STATUS_DISMISS:
            if not job_store:
                raise dash.exceptions.PreventUpdate
            return (
                *default_graph_outputs,
                {"status": "dismissed"},
                True,
                "",
                "",
                [],
                [],
                overlay_hidden,
            )

        if not job_store or not job_store.get("job_id"):
            raise dash.exceptions.PreventUpdate

        job_data = dict(job_store)
        job_id = job_data.get("job_id")
        status = JOB_MANAGER.status(job_id)
        now = time.time()
        settings_markup = _settings_badges(job_data.get("settings"))

        if status == "queued":
            job_data.setdefault("submitted", now)
            job_data["status"] = "queued"
            return (
                *default_graph_outputs,
                job_data,
                False,
                "Queued for execution…",
                "",
                [],
                settings_markup,
                "job-status-overlay",
            )

        if status == "running":
            job_data.setdefault("submitted", now)
            job_data.setdefault("started", now)
            job_data["status"] = "running"
            elapsed = now - job_data.get("started", now)
            runtime_text = f"Elapsed: {elapsed:.1f}s"
            return (
                *default_graph_outputs,
                job_data,
                False,
                "Running analysis…",
                runtime_text,
                [],
                settings_markup,
                "job-status-overlay",
            )

        if status == "failed":
            exception = JOB_MANAGER.exception(job_id)
            warning = f"Analysis job failed: {exception}" if exception else "Analysis job failed."
            graph_outputs = _error_outputs(warning)
            job_data = {
                "status": "failed",
                "message": warning,
                "settings": job_store.get("settings"),
            }
            return (
                *graph_outputs,
                job_data,
                True,
                "Analysis failed",
                "",
                _warnings_markup([warning]),
                _settings_badges(job_store.get("settings")),
                "job-status-overlay",
            )

        if status == "finished":
            payload = JOB_MANAGER.result(job_id)
            graph_outputs = _payload_to_outputs(payload)
            runtime_seconds = payload.get("runtime_seconds")
            if runtime_seconds is None and job_data.get("started"):
                runtime_seconds = now - job_data["started"]
            runtime_text = f"Runtime: {runtime_seconds:.1f}s" if runtime_seconds is not None else ""
            job_settings = payload.get("settings", job_data.get("settings"))
            job_data = {
                "status": "completed",
                "job_id": None,
                "completed": now,
                "warnings": payload.get("warnings", []),
                "runtime": runtime_seconds,
                "settings": job_settings,
            }
            status_text = "Analysis complete"
            return (
                *graph_outputs,
                job_data,
                True,
                status_text,
                runtime_text,
                _warnings_markup(payload.get("warnings", [])),
                _settings_badges(job_settings),
                "job-status-overlay",
            )

        raise dash.exceptions.PreventUpdate

    @app.callback(
        Output(ids.RUN_HISTORY_CONTAINER, "children"),
        Output(ids.RUN_HISTORY_EMPTY, "hidden"),
        Output(ids.STORE_HISTORY, "data"),
        Output(ids.BUTTON_DOWNLOAD_SAMPLE_REPORT, "disabled"),
        Input(ids.INTERVAL_HISTORY, "n_intervals"),
        Input(ids.STORE_RESULTS, "data"),
        prevent_initial_call=False,
    )
    def refresh_run_history(_tick, _store_results):
        runs = _list_recent_runs()
        sample_bundle = Path("artifacts/sample_report/crispr_studio_report_bundle.zip")
        sample_disabled = not sample_bundle.exists()
        if not runs:
            return [], False, {"runs": []}, sample_disabled

        history_items = [_build_history_item(run) for run in runs]
        history_group = dbc.ListGroup(history_items, flush=True, className="history-group")
        return history_group, True, {"runs": runs}, sample_disabled

    @app.callback(
        Output(ids.STORE_RESULTS, "data", allow_duplicate=True),
        Output(ids.GRAPH_VOLCANO, "figure", allow_duplicate=True),
        Output(ids.GRAPH_QC_REPLICATE, "figure", allow_duplicate=True),
        Output(ids.GRAPH_QC_DETECTION, "figure", allow_duplicate=True),
        Output(ids.GRAPH_PATHWAY_BUBBLE, "figure", allow_duplicate=True),
        Output(ids.SUMMARY_CARDS, "children", allow_duplicate=True),
        Output(ids.TABLE_GENES, "data", allow_duplicate=True),
        Output(ids.STORE_JOB, "data", allow_duplicate=True),
        Output(ids.INTERVAL_JOB, "disabled", allow_duplicate=True),
        Output(ids.JOB_STATUS_TEXT, "children", allow_duplicate=True),
        Output(ids.JOB_STATUS_RUNTIME, "children", allow_duplicate=True),
        Output(ids.JOB_STATUS_WARNINGS, "children", allow_duplicate=True),
        Output(ids.JOB_STATUS_SETTINGS, "children", allow_duplicate=True),
        Output(ids.JOB_STATUS_OVERLAY, "className", allow_duplicate=True),
        Input({"type": ids.RUN_HISTORY_ITEM, "run_id": ALL}, "n_clicks"),
        State(ids.STORE_HISTORY, "data"),
        prevent_initial_call=True,
    )
    def load_history_run(_n_clicks, history_store):
        triggered = callback_context.triggered
        if not triggered:
            raise dash.exceptions.PreventUpdate
        triggered_id = callback_context.triggered_id
        if not isinstance(triggered_id, dict):
            raise dash.exceptions.PreventUpdate
        run_id = triggered_id.get("run_id")
        if not run_id or not history_store:
            raise dash.exceptions.PreventUpdate

        runs = {run["id"]: run for run in history_store.get("runs", [])}
        run_info = runs.get(run_id)
        if not run_info:
            raise dash.exceptions.PreventUpdate

        payload = _load_run_payload(Path(run_info["path"]))
        graph_outputs = _payload_to_outputs(payload)
        job_data = {"status": "history", "job_id": None, "settings": run_info.get("settings")}
        return (
            *graph_outputs,
            job_data,
            True,
            "",
            "",
            [],
            _settings_badges(run_info.get("settings")),
            "job-status-overlay hidden",
        )

    @app.callback(
        Output(ids.GENE_MODAL, "is_open"),
        Output(ids.GENE_MODAL_BODY, "children"),
        Output(ids.STORE_SELECTED_GENE, "data"),
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
        gene_symbol = row.get("gene")
        if not gene_symbol:
            raise dash.exceptions.PreventUpdate

        analysis = AnalysisResult.model_validate(result_store.get("result"))
        annotations = result_store.get("annotations", {})
        gene_info = next((g for g in analysis.gene_results if g.gene_symbol == gene_symbol), None)
        annotation = annotations.get(gene_symbol, {}) or {}

        guides = gene_info.guides if gene_info else []
        spark_points = [(guide.guide_id, guide.log2_fold_change) for guide in guides if guide.log2_fold_change is not None]
        if spark_points:
            sparkline_fig = go.Figure()
            sparkline_fig.add_trace(
                go.Scatter(
                    x=[pt[0] for pt in spark_points],
                    y=[pt[1] for pt in spark_points],
                    mode="lines+markers",
                    marker=dict(color="#7f5af0", size=8),
                    line=dict(width=2),
                )
            )
            sparkline_fig.update_layout(
                height=220,
                margin=dict(l=30, r=20, t=30, b=40),
                title="Guide log2FC profile",
                yaxis_title="log2FC",
                template="plotly_dark",
            )
            sparkline = dcc.Graph(id=ids.GENE_SPARKLINE, figure=sparkline_fig, config={"displayModeBar": False}, className="gene-sparkline")
        else:
            sparkline = html.Div("Guide-level log2FC data unavailable for this gene.", className="gene-sparkline-empty")

        def _format_metric(value: Any, precision: int = 3) -> str:
            if value is None:
                return "—"
            if isinstance(value, (int, float)):
                return f"{value:.{precision}f}"
            return str(value)

        metrics = [
            ("Score", _format_metric(gene_info.score if gene_info else row.get("score"))),
            ("FDR", _format_metric(gene_info.fdr if gene_info else row.get("fdr"))),
            ("log2FC", _format_metric(gene_info.log2_fold_change if gene_info else row.get("log2_fold_change"))),
            ("Guides", gene_info.n_guides if gene_info else row.get("n_guides", "—")),
        ]

        metrics_grid = html.Div(
            [
                html.Div([
                    html.Small(label.upper(), className="metric-label"),
                    html.Strong(value, className="metric-value"),
                ])
                for label, value in metrics
            ],
            className="gene-metric-grid",
        )

        badges = []
        symbol_badge = annotation.get("symbol") or gene_symbol
        if symbol_badge:
            badges.append(dbc.Badge(symbol_badge, color="primary", className="gene-badge"))
        entrez = annotation.get("entrez_id") or annotation.get("entrezgene")
        if entrez:
            badges.append(dbc.Badge(f"Entrez {entrez}", color="secondary", className="gene-badge"))
        badge_row = html.Div(badges, className="gene-badge-row") if badges else None

        summary_text = annotation.get("summary") or "No annotation available."

        download_button = dbc.Button(
            "Download JSON",
            id=ids.GENE_DOWNLOAD_BUTTON,
            color="secondary",
            outline=True,
            className="gene-download-btn",
        )

        body = html.Div(
            [
                html.Div([
                    html.H4(gene_symbol, className="gene-modal-title"),
                    badge_row,
                ], className="gene-header"),
                metrics_grid,
                sparkline,
                html.Hr(),
                html.P(summary_text, className="gene-summary"),
                download_button,
            ],
            className="gene-modal-content",
        )

        selected_gene_data = {
            "gene": gene_symbol,
            "record": gene_info.model_dump(mode="json") if gene_info else None,
            "annotation": annotation,
        }

        return True, body, selected_gene_data

    @app.callback(
        Output(ids.DOWNLOAD_GENE, "data"),
        Input(ids.GENE_DOWNLOAD_BUTTON, "n_clicks"),
        State(ids.STORE_SELECTED_GENE, "data"),
        prevent_initial_call=True,
    )
    def download_gene_details(n_clicks, gene_data):
        if not gene_data:
            raise dash.exceptions.PreventUpdate
        gene_symbol = gene_data.get("gene", "gene")
        content = json.dumps(gene_data, indent=2)
        filename = f"{gene_symbol.lower()}_details.json"
        return dict(content=content, filename=filename)

    @app.callback(
        Output(ids.DOWNLOAD_SAMPLE_REPORT, "data"),
        Input(ids.BUTTON_DOWNLOAD_SAMPLE_REPORT, "n_clicks"),
        prevent_initial_call=True,
    )
    def download_sample_report(_n_clicks):
        bundle = Path("artifacts/sample_report/crispr_studio_report_bundle.zip")
        if not bundle.exists():
            raise dash.exceptions.PreventUpdate
        return dcc.send_file(str(bundle))

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
