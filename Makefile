PYTHON ?= python3.11
PACKAGE := crispr_screen_expert

.PHONY: install lint format test run-app build-report benchmark clean api-example

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

api-example:
	@mkdir -p artifacts
	@echo "Launching local API server and exercising examples/api_client.py"
	@UVICORN_CMD="$(PYTHON) -m uvicorn crispr_screen_expert.api:create_app --factory --host 127.0.0.1 --port 8000"; \
	($$UVICORN_CMD > artifacts/api_client_server.log 2>&1 &) && echo $$! > artifacts/api_server.pid; \
	sleep 3; \
	$(PYTHON) examples/api_client.py --host http://127.0.0.1:8000; \
	kill $$(cat artifacts/api_server.pid) 2>/dev/null || true; \
	rm -f artifacts/api_server.pid

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache logs artifacts .cache
