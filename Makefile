PYTHON := python3
PACKAGE := crispr_screen_expert

.PHONY: install lint format test run-app build-report benchmark clean

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .[dev,docs]

lint:
	ruff check .
	mypy src

format:
	ruff check --fix .

test:
	pytest --cov=$(PACKAGE) --cov-report=term-missing

run-app:
	@echo "Dash application not implemented yet. Implement via Prompt 19+ before running."

build-report:
	$(PYTHON) scripts/build_report.py

benchmark:
	$(PYTHON) -m pip install -e .[benchmark]
	$(PYTHON) scripts/benchmark_pipeline.py

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache logs artifacts .cache
