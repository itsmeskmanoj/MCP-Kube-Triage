from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from kube_triage.clients.prometheus import METRIC_CATALOG
from kube_triage.skills.loader import Skill, SkillRegistry

READ_ONLY_POLICY = """# Read-only Safety Contract

The MCP server performs parameterized inventory `SELECT` queries, approved
Prometheus reads, bounded correlation, and local knowledge reads only.
The MCP server never executes commands.

It has no kubeconfig, Kubernetes credentials, shell, SSH, subprocess, cloud CLI,
or application CLI capability. It never creates, applies, patches, edits, scales,
restarts, or deletes workloads. It never mutates databases, Prometheus, files, or
monitoring configuration through an MCP operation.

Commands in skills and prompt output are display-only guidance. The operator must
review every command, replace `<context>` with the intended Kubernetes context,
and run it in the operator's authenticated local terminal. Mutating remediation
remains operator-owned and is never executed automatically.
"""

INVENTORY_SCHEMA = """# Deployment Inventory Schema

The `deployments` table is addressed by the unique key
`(cluster_name, namespace, deployment_name)`.

| Field | Meaning |
| --- | --- |
| `id` | Inventory row identifier. |
| `cluster_name` | Required cluster discriminator. |
| `namespace` | Kubernetes namespace. |
| `deployment_name` | Kubernetes deployment name. |
| `application_name` | Logical application. |
| `environment` | Environment classification. |
| `owner_team` | Owning team. |
| `image` | Expected workload image. |
| `desired_replicas` | Expected replica count. |
| `cpu_request_cores` | Deployment CPU request used for comparison. |
| `memory_request_bytes` | Deployment memory request used for comparison. |
| `created_at` | Inventory creation timestamp. |
| `updated_at` | Inventory freshness timestamp. |
"""


def _metric_catalog_markdown() -> str:
    rows = [
        "# Approved Metric Catalog",
        "",
        "All queries require a `cluster` label. Deployment-scoped metrics also require ",
        "`namespace` and `deployment`. Arbitrary PromQL is not accepted.",
        "",
        "| Approved name | Prometheus metric or rule | Scope | Purpose |",
        "| --- | --- | --- | --- |",
    ]
    for name, definition in METRIC_CATALOG.items():
        scope = "deployment" if definition["deployment_scoped"] else "cluster"
        rows.append(
            f"| `{name.value}` | `{definition['metric']}` | {scope} | "
            f"{definition['description']} |"
        )
    rows.extend(
        [
            "",
            "Range queries are limited by `PROMETHEUS_MAX_RANGE_HOURS`, use at least ",
            "`PROMETHEUS_MIN_STEP_SECONDS`, and reject responses above the configured limit.",
        ]
    )
    return "\n".join(rows)


def _skill_reader(skill: Skill) -> Callable[[], str]:
    def read_skill_resource() -> str:
        return skill.markdown

    read_skill_resource.__name__ = f"skill_{skill.metadata.id.replace('/', '_')}"
    return read_skill_resource


def register_resources(server: FastMCP, skills: SkillRegistry) -> None:
    @server.resource("policy://kube-triage/read-only", mime_type="text/markdown")
    def read_only_policy() -> str:
        """Safety and local CLI execution contract."""
        return READ_ONLY_POLICY

    @server.resource("catalog://kube-triage/metrics", mime_type="text/markdown")
    def metric_catalog() -> str:
        """Approved metrics, recording rules, and expected labels."""
        return _metric_catalog_markdown()

    @server.resource(
        "catalog://kube-triage/inventory-schema",
        mime_type="text/markdown",
    )
    def inventory_schema() -> str:
        """Deployment inventory fields and target key."""
        return INVENTORY_SCHEMA

    for skill in skills.list_skills():
        server.resource(
            skill.uri,
            name=f"skill_{skill.metadata.name}",
            description=skill.metadata.description,
            mime_type="text/markdown",
        )(_skill_reader(skill))
