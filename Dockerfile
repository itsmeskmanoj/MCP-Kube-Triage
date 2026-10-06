FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080 \
    DATABASE_URL=sqlite:///file:/app/data/inventory.db?mode=ro\&uri=true \
    PROMETHEUS_MODE=fixture \
    PROMETHEUS_FIXTURE_FILE=/app/fixtures/prometheus.json \
    SKILL_REGISTRY_DIR=/app/skill-registry \
    KNOWN_ISSUES_FILE=/app/known-issues/catalog.yaml

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

COPY fixtures ./fixtures
COPY skill-registry ./skill-registry
COPY known-issues ./known-issues
COPY scripts ./scripts

RUN mkdir -p /app/data \
    && python scripts/seed_inventory.py --database /app/data/inventory.db \
    && chown -R appuser:appuser /app/data

USER appuser
EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"]

CMD ["python", "-m", "kube_triage", "--transport", "streamable-http"]
