# Repository Instructions

- Preserve the read-only boundary: no subprocess, shell, Kubernetes client, kubeconfig, SSH, or mutating database/Prometheus operations in `src/`.
- Every dynamic inventory or telemetry request must include or resolve an explicit `cluster_name`.
- Keep expected failures in `ToolResultEnvelope` with the responsible component.
- Keep Prometheus access limited to `ApprovedMetric`; do not add arbitrary PromQL without an explicit design change.
- Commands in skills are display-only and must use `--context <context>`.
- Use the official MCP Python SDK v1 maintenance documentation for this pinned project:
  - https://py.sdk.modelcontextprotocol.io/v1/
  - https://py.sdk.modelcontextprotocol.io/v1/server/
  - https://py.sdk.modelcontextprotocol.io/v1/testing/
  - https://github.com/modelcontextprotocol/python-sdk/tree/v1.x
- Validate changes with `python -m ruff check .` and `python -m pytest`.