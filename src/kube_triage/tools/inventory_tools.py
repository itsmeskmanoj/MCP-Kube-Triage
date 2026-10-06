from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from kube_triage.clients.inventory import InventoryRepository
from kube_triage.models import ErrorComponent, ToolResultEnvelope
from kube_triage.tools.common import error_result

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


def register_inventory_tools(server: FastMCP, inventory: InventoryRepository) -> None:
    @server.tool(annotations=_READ_ONLY)
    def list_deployments(
        cluster_name: str | None = None,
        namespace: str | None = None,
        owner_team: str | None = None,
        application_name: str | None = None,
        limit: Annotated[int, Field(ge=1, le=1000)] = 100,
    ) -> ToolResultEnvelope:
        """List inventory deployments with optional exact-match filters."""
        try:
            deployments = inventory.list_deployments(
                cluster_name=cluster_name,
                namespace=namespace,
                owner_team=owner_team,
                application_name=application_name,
                limit=limit,
            )
            return ToolResultEnvelope.success(
                {
                    "deployments": [
                        item.model_dump(mode="json") for item in deployments
                    ],
                    "count": len(deployments),
                }
            )
        except Exception as exc:
            return error_result(exc, ErrorComponent.DATABASE)

    @server.tool(annotations=_READ_ONLY)
    def get_deployment(
        cluster_name: str,
        namespace: str,
        deployment_name: str,
    ) -> ToolResultEnvelope:
        """Get one deployment by cluster, namespace, and deployment name."""
        try:
            deployment = inventory.get_deployment(
                cluster_name,
                namespace,
                deployment_name,
            )
            if deployment is None:
                return ToolResultEnvelope.failure(
                    ErrorComponent.DATABASE,
                    "deployment_not_found",
                    "No deployment matched the complete cluster target",
                )
            return ToolResultEnvelope.success(
                {"deployment": deployment.model_dump(mode="json")}
            )
        except Exception as exc:
            return error_result(exc, ErrorComponent.DATABASE)
