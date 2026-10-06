# Kube Triage

A read-only multi-cluster Kubernetes operations server for Model Context Protocol
(MCP). Kube Triage correlates deployment inventory, Prometheus evidence, firing
alerts, and reusable Kubernetes troubleshooting procedures.

The repository is complete and runnable without a Kubernetes cluster. The default
demo uses a seeded SQLite inventory and deterministic Prometheus fixtures for two
clusters. It exposes the same MCP tools, resources, prompts, response envelopes,
and health correlation used by HTTP Prometheus and PostgreSQL deployments.

## Safety Boundary

The MCP runtime never:

- Executes `kubectl`, shell, SSH, cloud CLI, or application CLI commands.
- Reads kubeconfig or connects to a Kubernetes API.
- Creates, patches, edits, scales, restarts, or deletes workloads.
- Executes database writes or changes Prometheus configuration.
- Returns credentials, connection strings, raw environment variables, or Secrets.

Commands in skills are display-only. Every Kubernetes command includes
`--context <context>` and must be reviewed and run by the operator in an
authenticated local terminal. The demo seed script writes only the local SQLite
file during setup and is not imported or exposed by the MCP server.

## Architecture

```mermaid
flowchart LR
    USER[Operator] --> CLIENT[MCP AI Client]
    CLIENT <-->|Streamable HTTP or stdio| SERVER[Kubernetes Operations MCP Server]
    SERVER --> DB[(Read-only inventory)]
    SERVER --> PROM[Fixture or HTTP Prometheus]
    SERVER --> SKILLS[Validated skill registry]
    CLIENT -->|Displays context-explicit command| USER
    USER -->|Reviews and runs locally| CLI[Authenticated CLI]
    CLI --> K8S[(Selected cluster)]
```

## Quick Start Without a Cluster

Prerequisites: Python 3.12 and PowerShell.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts\seed_inventory.py
.\.venv\Scripts\python.exe -m kube_triage --transport streamable-http
```

The server listens on:

- MCP: `http://127.0.0.1:8080/mcp`
- Liveness: `http://127.0.0.1:8080/health`

The default database URL uses SQLite URI read-only mode. Running the seed script
again resets only the local demo inventory.

### Demo Scenarios

| Target | Expected state | Evidence |
| --- | --- | --- |
| `cluster-a/payments/payments-api` | `degraded` | 2/3 replicas, 7 restarts, warning alert |
| `cluster-a/checkout/checkout-api` | `critical` | 0/2 replicas, critical alert |
| `cluster-a/platform/event-consumer` | `unknown` | stale and missing metrics |
| `cluster-b/payments/payments-api` | `healthy` | 2/2 replicas, no alert or pressure signal |

The repeated `payments/payments-api` name proves that `cluster_name` remains part
of every dynamic target and prevents cross-cluster collisions.

## VS Code and MCP Inspector

[.vscode/mcp.json](.vscode/mcp.json) configures a local stdio server using the
workspace virtual environment. Use the VS Code MCP Servers view to start or debug
`kube-triage`.

For Streamable HTTP inspection, start the server and connect MCP Inspector to
`http://127.0.0.1:8080/mcp`:

```powershell
npx -y @modelcontextprotocol/inspector
```

## MCP Surface

### Tools

| Tool | Purpose |
| --- | --- |
| `search_skills` | Find at most two skills and matching sanitized known issues. |
| `get_skill_index` | List all valid skills and the malformed-file skip count. |
| `read_skill` | Read one skill by stable ID for clients without resource support. |
| `list_deployments` | List inventory with exact cluster, namespace, owner, or app filters. |
| `get_deployment` | Resolve one complete cluster/namespace/deployment target. |
| `prom_query` | Run one approved instant metric query. |
| `prom_query_range` | Run one approved bounded metric timeline query. |
| `get_firing_alerts` | Read firing alerts for an explicit cluster and optional target. |
| `deployment_health` | Correlate inventory, metrics, alerts, freshness, and skills. |

Every tool returns a `ToolResultEnvelope` with `ok`, `data`, `error`, and
`observed_at`. Expected failures identify `validation`, `database`, `prometheus`,
`knowledge`, or `correlation` as the responsible component.

### Resources

- `policy://kube-triage/read-only`
- `catalog://kube-triage/metrics`
- `catalog://kube-triage/inventory-schema`
- `skill://kube-triage/{category}/{name}` for all six loaded skills

### Prompts

- `deployment_health_check`
- `investigate_deployment`
- `cluster_health_summary`
- `investigate_unknown_issue`

Prompts tell the MCP client which tools to call. They do not collect data or run
commands themselves.

## Health Correlation

`deployment_health` evaluates:

- Inventory freshness and desired replicas.
- Live desired versus available replicas.
- One-hour restart increase.
- CPU usage versus the inventory CPU request.
- Memory working set versus the inventory memory request.
- Warning and critical firing alerts.
- Metric presence and freshness.

State precedence is deterministic:

1. `critical` when no desired replica is available or a critical alert fires.
2. `unknown` when required noncritical evidence is missing or stale.
3. `degraded` for replica mismatch, restart/resource thresholds, or warnings.
4. `healthy` only when all required evidence is fresh and no issue is present.

Facts, hypotheses, matched skills, alerts, and missing evidence remain separate in
the response.

## Approved Prometheus Contract

Kube Triage does not accept arbitrary PromQL. `ApprovedMetric` permits:

- `desired_replicas`
- `available_replicas`
- `restarts_last_1h`
- `cpu_usage_cores`
- `memory_working_set_bytes`
- `target_up`

Deployment queries always include cluster, namespace, and deployment selectors.
Range requests enforce a maximum duration and minimum step. HTTP requests enforce
a timeout and response-size limit. The expected normalized recording rules are:

- `deployment:container_cpu_usage:rate5m`
- `deployment:container_memory_working_set_bytes:sum`
- `deployment:pod_restarts:increase1h`

Each rule must expose `cluster`, `namespace`, and `deployment` labels.

## Connect Real Read-Only Data

Copy [.env.example](.env.example) to `.env` for local development, then override
only the values needed by the target environment.

For PostgreSQL:

```text
DATABASE_URL=postgresql+psycopg://inventory_reader:...@db.example/inventory
```

Grant the runtime role `CONNECT`, schema `USAGE`, and `SELECT` on the deployments
table only. Do not grant insert, update, delete, DDL, or ownership privileges.
All SQLAlchemy queries in the runtime are parameterized `SELECT` statements.

For Prometheus:

```text
PROMETHEUS_MODE=http
PROMETHEUS_URL=https://prometheus.example
PROMETHEUS_CLUSTER_LABEL=cluster
```

Optional basic-auth values are consumed as secrets and are never included in MCP
resources, tool responses, or logs. The server still requires no kubeconfig or
Kubernetes credentials.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `MCP_SERVER_NAME` | `kube-triage` | Advertised server name. |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8080` | HTTP bind address. |
| `DATABASE_URL` | read-only demo SQLite URI | Inventory connection. |
| `PROMETHEUS_MODE` | `fixture` | `fixture` or `http`. |
| `PROMETHEUS_URL` | empty | Required only in HTTP mode. |
| `PROMETHEUS_TIMEOUT_SECONDS` | `15` | HTTP request timeout. |
| `PROMETHEUS_MAX_RANGE_HOURS` | `24` | Maximum timeline duration. |
| `PROMETHEUS_MIN_STEP_SECONDS` | `30` | Minimum timeline step. |
| `PROMETHEUS_MAX_RESPONSE_BYTES` | `2000000` | Maximum HTTP response body. |
| `METRIC_STALE_AFTER_SECONDS` | `300` | Metric freshness threshold. |
| `INVENTORY_STALE_AFTER_HOURS` | `168` | Inventory freshness threshold. |
| `HEALTH_RESTART_WARNING` | `5` | Restart degradation threshold. |
| `HEALTH_CPU_WARNING_RATIO` | `0.9` | CPU request ratio threshold. |
| `HEALTH_MEMORY_WARNING_RATIO` | `0.9` | Memory request ratio threshold. |
| `SKILL_REGISTRY_DIR` | `./skill-registry` | Markdown skill root. |
| `KNOWN_ISSUES_FILE` | `./known-issues/catalog.yaml` | Sanitized issue catalog. |
| `LOG_LEVEL` | `INFO` | Structured stderr log level. |

## Docker

```powershell
docker compose up --build
```

The image runs as a non-root user, has all Linux capabilities dropped by Compose,
uses a read-only container filesystem, and binds port 8080 to localhost. The demo
database is seeded at build time and opened read-only at runtime.

## Development

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m build
```

Tests use the official SDK's in-memory client transport. They cover tool/resource/
prompt discovery, structured protocol results, all four health states, exact and
natural-language skill discovery, multi-cluster isolation, Prometheus bounds,
SELECT-only query paths, and the absence of subprocess/Kubernetes client imports.

## Project Layout

```text
src/kube_triage/        MCP server, adapters, tools, resources, prompts
skill-registry/         Validated Markdown investigation procedures
known-issues/           Sanitized reusable failure patterns
fixtures/               Deterministic Prometheus demo evidence
scripts/                Setup-only local inventory seeding
tests/                  Unit, protocol, and safety tests
```

The server uses the official MCP Python SDK v1 maintenance line pinned in
[pyproject.toml](pyproject.toml). The corresponding SDK references are recorded in
[.github/copilot-instructions.md](.github/copilot-instructions.md).
