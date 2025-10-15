# Prompt 02 – Repository Scaffolding & Tooling

Initialize the project skeleton without disturbing existing files. Create:
- `pyproject.toml` using PEP 621 for package `crispr_screen_expert` (Python 3.11), declaring runtime deps: pandas, numpy, scipy, scikit-learn, plotly, dash, dash-bootstrap-components, gseapy, mygene, requests, typer, jinja2, weasyprint, pydantic, pydantic-settings, loguru. Add optional extras `dev` (pytest, pytest-cov, ruff, mypy, types-requests), `docs` (mkdocs, mkdocs-material), `llm` (openai).
- `.gitignore` (Python + Dash app artifacts), `LICENSE` (MIT), `README.md` with project overview, quickstart placeholders, and table referencing forthcoming docs.
- `Makefile` exposing targets: `install`, `lint` (ruff + mypy), `format` (ruff --fix), `test`, `run-app`, `build-report`, `clean`.
- `src/crispr_screen_expert/__init__.py` exporting `__version__`.
- `setup.cfg` configuring pytest, mypy strict mode, and ruff rules (enable E, F, I; select pydocstyle Google convention).

Ensure README mentions Python 3.11, virtualenv instructions, Makefile usage, and cites `overview.md` as background.
