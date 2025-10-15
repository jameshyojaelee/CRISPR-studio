FROM python:3.11-slim AS builder

ARG BUILD_NATIVE=0
ENV PYTHONUNBUFFERED=1
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml setup.cfg README.md ./
COPY src ./src
COPY templates ./templates
COPY cpp ./cpp
COPY rust ./rust

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake ninja-build rustc cargo \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip \
    && if [ "${BUILD_NATIVE}" = "1" ]; then \
         pip install --no-cache-dir .[native]; \
         maturin develop --manifest-path rust/Cargo.toml --release; \
         python -m scikit_build_core.build --wheel -S cpp -b cpp/build/docker -o cpp/dist; \
         pip install cpp/dist/*.whl; \
       else \
         pip install --no-cache-dir .; \
       fi

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8050
ARG BUILD_NATIVE=0
ENV BUILD_NATIVE=${BUILD_NATIVE}

WORKDIR /app

COPY --from=builder /usr/local /usr/local
COPY . /app

EXPOSE 8050

CMD ["python", "app.py"]
