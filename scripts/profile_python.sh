#!/usr/bin/env bash
# Profile the Python pipeline using cProfile and py-spy.

set -euo pipefail

if [[ "${ENABLE_PROFILING:-0}" != "1" ]]; then
  echo "ENABLE_PROFILING=1 not set. Export it to acknowledge profiling mode." >&2
  exit 1
fi

COUNTS_PATH="${1:-sample_data/demo_counts.csv}"
LIBRARY_PATH="${2:-sample_data/demo_library.csv}"
METADATA_PATH="${3:-sample_data/demo_metadata.json}"
OUTPUT_ROOT="${PROFILING_OUTPUT:-artifacts/profiles/python}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
PROFILE_DIR="${OUTPUT_ROOT}/${TIMESTAMP}"
RUN_OUTPUT="${PROFILE_DIR}/runs"

mkdir -p "${PROFILE_DIR}" "${RUN_OUTPUT}"

PROFILE_CMD=(python -m crispr_screen_expert.cli run-pipeline "${COUNTS_PATH}" "${LIBRARY_PATH}" "${METADATA_PATH}" \
  --use-mageck False --output-root "${RUN_OUTPUT}")

echo "[profiling] Running cProfile"
python -m cProfile -o "${PROFILE_DIR}/pipeline.cprofile" -m crispr_screen_expert.cli \
  run-pipeline "${COUNTS_PATH}" "${LIBRARY_PATH}" "${METADATA_PATH}" --use-mageck False --output-root "${RUN_OUTPUT}" >/dev/null

echo "[profiling] Generating py-spy flamegraph (if available)"
if command -v py-spy >/dev/null 2>&1; then
  py-spy record --output "${PROFILE_DIR}/py-spy.svg" -- python -m crispr_screen_expert.cli \
    run-pipeline "${COUNTS_PATH}" "${LIBRARY_PATH}" "${METADATA_PATH}" --use-mageck False --output-root "${RUN_OUTPUT}" >/dev/null
else
  echo "py-spy not found on PATH; skipping flamegraph generation." >&2
fi

echo "Artifacts written to ${PROFILE_DIR}"
