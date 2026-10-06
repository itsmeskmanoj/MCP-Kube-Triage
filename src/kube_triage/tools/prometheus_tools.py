from datetime import datetime
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from kube_triage.clients.prometheus import ApprovedMetric, PrometheusClient
from kube_triage.models import ErrorComponent, ToolResultEnvelope
from kube_triage.tools.common import error_result

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def register_prometheus_tools(server: FastMCP, prometheus: PrometheusClient) -> None:
    @server.tool(annotations=_READ_ONLY)
    async def prom_query(
        metric: ApprovedMetric,
        cluster_name: str,
        namespace: str | None = None,
        deployment: str | None = None,
    ) -> ToolResultEnvelope:
        """Run one approved instant metric query for an explicit cluster."""
        try:
            result = await prometheus.query(
                metric,
                cluster_name,
                namespace,
                deployment,
            )
            return ToolResultEnvelope.success(
                {"result": result.model_dump(mode="json")}
            )
        except Exception as exc:
            return error_result(exc, ErrorComponent.PROMETHEUS)

    @server.tool(annotations=_READ_ONLY)
    async def prom_query_range(
        metric: ApprovedMetric,
        cluster_name: str,
        start: str,
        end: str,
        step_seconds: Annotated[int, Field(ge=1)],
        namespace: str | None = None,
        deployment: str | None = None,
    ) -> ToolResultEnvelope:
        """Run one approved, bounded range query for an explicit cluster."""
        try:
            try:
                parsed_start = _parse_timestamp(start)
                parsed_end = _parse_timestamp(end)
            except ValueError as exc:
                from kube_triage.errors import ValidationError

                raise ValidationError(
                    "invalid_timestamp",
                    "start and end must be RFC3339 timestamps",
                ) from exc
            result = await prometheus.query_range(
                metric,
                cluster_name,
                parsed_start,
                parsed_end,
                step_seconds,
                namespace,
                deployment,
            )
            return ToolResultEnvelope.success(
                {"result": result.model_dump(mode="json")}
            )
        except Exception as exc:
            return error_result(exc, ErrorComponent.PROMETHEUS)

    @server.tool(annotations=_READ_ONLY)
    async def get_firing_alerts(
        cluster_name: str,
        namespace: str | None = None,
        deployment: str | None = None,
    ) -> ToolResultEnvelope:
        """Return firing alerts for a cluster and optional deployment scope."""
        try:
            alerts = await prometheus.get_firing_alerts(
                cluster_name,
                namespace,
                deployment,
            )
            return ToolResultEnvelope.success(
                {
                    "alerts": [alert.model_dump(mode="json") for alert in alerts],
                    "count": len(alerts),
                }
            )
        except Exception as exc:
            return error_result(exc, ErrorComponent.PROMETHEUS)
