# Notebook Quickstart

Sometimes it's easier to show a friend the workflow inside Colab than to explain the CLI over a call. The `notebooks/quickstart.ipynb` notebook mirrors the demo pipeline end-to-end without needing MAGeCK or live annotations.

## Launch options
- **Colab** – click the badge in the README or open: https://colab.research.google.com/github/jameshyojaelee/CRISPR-studio/blob/main/notebooks/quickstart.ipynb
  - Run the first cell to install the package: `pip install "crispr_screen_expert[reports]"`.
  - Files are pulled from the repo automatically; no uploads needed unless you change the paths.
- **Local Jupyter** – activate your virtualenv, then `jupyter lab` (or `notebook`) from the repo root so the relative paths resolve.

## What the notebook does
1. Points at `sample_data/` by default. Change `DATA_DIR` in the setup cell to use your own counts/library/metadata.
2. Calls the same validation routine used by the CLI, so contract violations are caught early.
3. Runs the pipeline with `use_mageck=False`, `skip_annotations=True`, and no Enrichr libraries to keep runtime under two minutes on Colab hardware.
4. Builds a tiny summary table plus Plotly figures for the top genes and warnings.

## Tips
- If you need annotations, flip `SKIP_ANNOTATIONS` to `False` once you're on a reliable network.
- Results are written under `artifacts/notebooks/` when run locally; clean it out between demos if you want a fresh slate.
- For larger datasets, consider exporting a filtered subset first—the notebook is tuned for quick sanity checks, not overnight jobs.
