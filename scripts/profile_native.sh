#!/usr/bin/env bash
# Profile native extensions using perf and valgrind callgrind.

set -euo pipefail

if [[ "${ENABLE_PROFILING:-0}" != "1" ]]; then
  echo "ENABLE_PROFILING=1 not set. Export it to acknowledge profiling mode." >&2
  exit 1
fi

COUNTS_PATH="${1:-sample_data/demo_counts.csv}"
LIBRARY_PATH="${2:-sample_data/demo_library.csv}"
METADATA_PATH="${3:-sample_data/demo_metadata.json}"
OUTPUT_ROOT="${PROFILING_OUTPUT:-artifacts/profiles/native}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
PROFILE_DIR="${OUTPUT_ROOT}/${TIMESTAMP}"
RUN_OUTPUT="${PROFILE_DIR}/runs"

mkdir -p "${PROFILE_DIR}" "${RUN_OUTPUT}"

BASE_CMD=(python -m crispr_screen_expert.cli run-pipeline "${COUNTS_PATH}" "${LIBRARY_PATH}" "${METADATA_PATH}" \
  --use-mageck False --use-native-rra --use-native-enrichment --output-root "${RUN_OUTPUT}")

if command -v perf >/dev/null 2>&1; then
  echo "[profiling] Collecting perf data"
  perf record -F "${PERF_FREQ:-199}" -g --output "${PROFILE_DIR}/perf.data" -- "${BASE_CMD[@]}" >/dev/null
  perf script --input "${PROFILE_DIR}/perf.data" > "${PROFILE_DIR}/perf.script"
  if [[ -n "${FLAMEGRAPH_DIR:-}" && -x "${FLAMEGRAPH_DIR}/stackcollapse-perf.pl" && -x "${FLAMEGRAPH_DIR}/flamegraph.pl" ]]; then
    "${FLAMEGRAPH_DIR}/stackcollapse-perf.pl" "${PROFILE_DIR}/perf.script" | \
      "${FLAMEGRAPH_DIR}/flamegraph.pl" > "${PROFILE_DIR}/perf-flamegraph.svg"
  else
    echo "FlameGraph utilities not configured; skipping perf flamegraph." >&2
  fi
else
  echo "perf not found on PATH; skipping perf profiling." >&2
fi

if command -v valgrind >/dev/null 2>&1; then
  echo "[profiling] Running valgrind callgrind"
  valgrind --tool=callgrind --callgrind-out-file="${PROFILE_DIR}/callgrind.out" "${BASE_CMD[@]}" >/dev/null
else
  echo "valgrind not found on PATH; skipping callgrind run." >&2
fi

echo "Native profiling artifacts written to ${PROFILE_DIR}"
