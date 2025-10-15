FROM python:3.11-slim AS builder

WORKDIR /app

COPY pyproject.toml setup.cfg README.md ./
COPY src ./src
COPY templates ./templates

RUN pip install --upgrade pip \
    && pip install --no-cache-dir .

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8050

WORKDIR /app

COPY --from=builder /usr/local /usr/local
COPY . /app

EXPOSE 8050

CMD ["python", "app.py"]
