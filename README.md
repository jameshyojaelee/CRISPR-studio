# CRISPR-studio

CRISPR-studio is a next-generation analysis and visualization toolkit that turns pooled CRISPR screen data into interactive biological insights. The planning brief in `overview.md` drives the scope: automated QC, MAGeCK-compatible hit calling, pathway enrichment, curated gene context, and narrative-ready reporting for demos and admissions showcases.

> **Status:** Repository scaffolding only. Use the prompts in `codex_prompts.md` to continue building the system module-by-module.

## Getting Started

### Prerequisites
- Python 3.11 (recommended to manage via `pyenv` or system package manager)
- A virtual environment tool such as `python3 -m venv` or `conda`

### Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install .
```
Alternatively, use the provided `Makefile` targets once dependencies are installed (described below).

### Makefile Targets
| Target | Description |
| --- | --- |
| `make install` | Install the package with development extras. |
| `make lint` | Run `ruff` and `mypy` linting. |
| `make format` | Apply formatting fixes via `ruff --fix`. |
| `make test` | Execute the pytest suite with coverage once tests exist. |
| `make run-app` | Launch the Dash web application (placeholder). |
| `make build-report` | Build static reports (placeholder). |
| `make clean` | Remove build artifacts and caches. |

### Quickstart (Placeholder)
1. Create or activate a Python 3.11 virtual environment.
2. Install the package and extras using `make install`.
3. Follow the build prompts in `codex_prompts.md` to generate data contracts, pipeline components, and the Dash UI.

#### Demo Dataset
- Sample inputs live in `sample_data/` (`demo_counts.csv`, `demo_library.csv`, `demo_metadata.json`) and adhere to the contract in `docs/data_contract.md`.
- Regenerate or customize the synthetic dataset with `python scripts/generate_demo_dataset.py --output-dir sample_data --seed 42`.
- The demo models a dropout screen with two control and two treatment replicates, highlighting DNA repair genes that deplete under drug selection.

## Documentation Roadmap

| Document | Purpose | Status |
| --- | --- | --- |
| `docs/data_contract.md` | Define input expectations for counts, library, metadata. | Planned |
| `docs/user_guide.md` | Walkthrough for CLI and Dash usage. | Planned |
| `docs/developer_guide.md` | Architecture and contribution guidance. | Planned |
| `docs/roadmap.md` | Milestones and success metrics. | Planned |
| `docs/security_privacy.md` | Data handling checklist. | Planned |

Refer to `overview.md` for the full product vision, demo script, and go-to-market context guiding subsequent development prompts.
