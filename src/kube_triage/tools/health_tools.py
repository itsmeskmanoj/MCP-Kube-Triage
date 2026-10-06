from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from kube_triage.health import HealthCorrelator
from kube_triage.models import ErrorComponent, ToolResultEnvelope
from kube_triage.tools.common import error_result

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


def register_health_tools(server: FastMCP, correlator: HealthCorrelator) -> None:
    @server.tool(annotations=_READ_ONLY)
    async def deployment_health(
        cluster_name: str,
        namespace: str,
        deployment: str,
    ) -> ToolResultEnvelope:
        """Correlate inventory, metrics, alerts, and skills for one deployment."""
        try:
            assessment = await correlator.evaluate(
                cluster_name,
                namespace,
                deployment,
            )
            return ToolResultEnvelope.success(
                {"health": assessment.model_dump(mode="json")}
            )
        except Exception as exc:
            return error_result(exc, ErrorComponent.CORRELATION)