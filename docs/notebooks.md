# Notebook Quickstart

Launch the Colab-friendly quickstart to validate the sample dataset and run the pipeline without MAGeCK or online annotations.

- Prerequisites: Python 3.11+ and `pip install "crispr_screen_expert[reports]"`. In Colab, run the install cell in the notebook.
- Open in Colab: https://colab.research.google.com/github/jameshyojaelee/CRISPR-studio/blob/main/notebooks/quickstart.ipynb
- Local run: execute the notebook from the repository root so `../sample_data/` resolves correctly. Results are written under `artifacts/notebooks/`.
- Adapt to your data: update `DATA_DIR` in the setup cell to point at your counts, library, and metadata files. The notebook validates the contract via `data_loader` before running.
- Offline-friendly: the pipeline uses `use_mageck=False`, `cache_annotations=False`, and empty `enrichr_libraries` to avoid network calls. Adjust those settings for full analyses.

If execution time exceeds two minutes, first confirm you are using the bundled sample data, then consider reducing replicate counts or disabling enrichment in custom datasets.
