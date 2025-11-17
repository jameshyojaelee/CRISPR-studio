"""Shared UI constants for the Dash experience."""

from __future__ import annotations

from typing import List, Dict

DEFAULT_PIPELINE_SETTINGS = {
    "use_mageck": True,
    "use_native_rra": False,
    "use_native_enrichment": False,
    "enrichr_libraries": [],
    "skip_annotations": False,
}

ENRICHR_LIBRARY_OPTIONS: List[Dict[str, str]] = [
    {"label": "MSigDB Hallmark 2020", "value": "MSigDB_Hallmark_2020"},
    {"label": "GO Biological Process 2021", "value": "GO_Biological_Process_2021"},
    {"label": "KEGG 2019 Human", "value": "KEGG_2019_Human"},
    {"label": "Reactome 2016", "value": "Reactome_2016"},
    {"label": "Native demo", "value": "native_demo"},
]
"""Curated options exposed in the Enrichr dropdown."""
