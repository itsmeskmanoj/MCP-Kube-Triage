from mcp.server.fastmcp import FastMCP

_SAFETY = (
    "Never claim that the MCP server ran a command. Any kubectl or CLI command must be "
    "display-only, include `--context <context>`, and be run by the user after review."
)


def register_prompts(server: FastMCP) -> None:
    @server.prompt(title="Deployment health check")
    def deployment_health_check(cluster: str, namespace: str, deployment: str) -> str:
        """Assess one deployment from inventory and telemetry evidence."""
        return f"""Assess deployment `{deployment}` in namespace `{namespace}` on cluster
`{cluster}`.

1. Call `get_deployment` with all three target fields.
2. Call `deployment_health` for the same complete target.
3. If evidence is missing, use only the narrowly required approved metric or alert tools.
4. Report status, timestamped facts, hypotheses, missing evidence, and matched skills separately.
5. Do not report healthy when required evidence is missing or stale.

{_SAFETY}
"""

    @server.prompt(title="Investigate deployment")
    def investigate_deployment(
        cluster: str,
        namespace: str,
        deployment: str,
        symptom: str = "",
    ) -> str:
        """Investigate one deployment using skills and discriminating evidence."""
        symptom_text = symptom or "no symptom supplied"
        return f"""Investigate `{deployment}` in `{namespace}` on `{cluster}`. Reported
symptom: {symptom_text}.

1. Resolve inventory using the complete cluster target.
2. Search skills using an exact alert code when available, otherwise the symptom.
3. Read no more than two matching skills.
4. Call `deployment_health`, then gather only evidence that distinguishes the leading hypotheses.
5. Return an RCA-style summary with facts, likely causes, uncertainty, missing evidence,
   next read-only checks, and operator-owned remediation clearly separated.

{_SAFETY}
"""

    @server.prompt(title="Cluster health summary")
    def cluster_health_summary(cluster: str, namespace: str = "") -> str:
        """Rank unhealthy or unknown deployments in one selected cluster."""
        scope = f"namespace `{namespace}`" if namespace else "all namespaces"
        return f"""Summarize deployment health for {scope} in cluster `{cluster}`.

1. Call `list_deployments` with `cluster_name={cluster}` and the namespace filter if supplied.
2. Evaluate each returned deployment with `deployment_health`, preserving the cluster target.
3. Rank critical first, then degraded, unknown, and healthy.
4. Keep evidence concise and identify data gaps instead of inventing conclusions.

{_SAFETY}
"""

    @server.prompt(title="Investigate unknown issue")
    def investigate_unknown_issue(
        cluster: str,
        namespace: str,
        deployment: str,
        symptom: str,
    ) -> str:
        """Use a baseline workflow when no reusable skill matches."""
        return f"""No reusable procedure matched `{symptom}` for `{deployment}` in
`{namespace}` on `{cluster}`.

1. State explicitly that no skill matched.
2. Resolve inventory and call `deployment_health`.
3. Gather replica, restart, CPU, memory, and firing-alert evidence only through approved tools.
4. Separate observed facts from hypotheses and list every missing or stale signal.
5. Suggest the smallest next read-only local checks needed to discriminate hypotheses.

{_SAFETY}
"""
