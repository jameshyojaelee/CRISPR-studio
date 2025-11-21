ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

FROM base AS builder
ARG BUILD_NATIVE=0
ENV PATH="/root/.cargo/bin:${PATH}"

COPY pyproject.toml setup.cfg README.md ./
COPY src ./src
COPY templates ./templates
COPY cpp ./cpp
COPY rust ./rust
COPY assets ./assets
COPY resources ./resources
COPY sample_data ./sample_data

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        git \
        curl \
    && if [ "${BUILD_NATIVE}" = "1" ]; then \
         apt-get install -y --no-install-recommends cmake ninja-build rustc cargo; \
       fi \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

RUN pip install --no-cache-dir ".[reports]" \
    && if [ "${BUILD_NATIVE}" = "1" ]; then \
         pip install --no-cache-dir ".[native]"; \
         maturin develop --manifest-path rust/Cargo.toml --release; \
         python -m scikit_build_core.build --wheel -S cpp -b cpp/build/docker -o cpp/dist; \
         pip install cpp/dist/*.whl; \
       fi

FROM base AS runtime
ARG BUILD_NATIVE=0
ENV BUILD_NATIVE=${BUILD_NATIVE} \
    PORT=8050 \
    API_PORT=8000
WORKDIR /app

COPY --from=builder /usr/local /usr/local
COPY app.py app_api.py ./ 
COPY src ./src
COPY assets ./assets
COPY templates ./templates
COPY resources ./resources
COPY sample_data ./sample_data
COPY artifacts/sample_report ./artifacts/sample_report

RUN groupadd --system crispr && useradd --system --gid crispr --home-dir /home/crispr --create-home crispr \
    && chown -R crispr:crispr /app

USER crispr

EXPOSE 8050 8000

CMD ["python", "app.py"]
