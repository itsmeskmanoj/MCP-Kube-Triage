from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from kube_triage import __version__
from kube_triage.clients.inventory import InventoryRepository
from kube_triage.clients.prometheus import PrometheusClient, create_prometheus_client
from kube_triage.config import Settings
from kube_triage.health import HealthCorrelator
from kube_triage.known_issues.loader import KnownIssueRegistry
from kube_triage.logging_config import configure_logging
from kube_triage.prompts.workflows import register_prompts
from kube_triage.resources.registry import register_resources
from kube_triage.skills.loader import SkillRegistry
from kube_triage.tools.health_tools import register_health_tools
from kube_triage.tools.inventory_tools import register_inventory_tools
from kube_triage.tools.knowledge_tools import register_knowledge_tools
from kube_triage.tools.prometheus_tools import register_prometheus_tools


def create_server(
    settings: Settings | None = None,
    *,
    inventory: InventoryRepository | None = None,
    prometheus: PrometheusClient | None = None,
    skills: SkillRegistry | None = None,
    known_issues: KnownIssueRegistry | None = None,
) -> FastMCP:
    resolved = settings or Settings()
    configure_logging(resolved.log_level)
    resolved_inventory = inventory or InventoryRepository(
        resolved.database_url,
        max_rows=resolved.inventory_max_rows,
    )
    resolved_prometheus = prometheus or create_prometheus_client(resolved)
    resolved_skills = skills or SkillRegistry.load(resolved.skill_registry_dir)
    resolved_known_issues = known_issues or KnownIssueRegistry.load(
        resolved.known_issues_file,
        resolved_skills,
    )
    correlator = HealthCorrelator(
        resolved_inventory,
        resolved_prometheus,
        resolved_skills,
        resolved,
    )
    server = FastMCP(
        resolved.mcp_server_name,
        instructions=(
            "Read-only Kubernetes operations evidence server. It never executes commands or "
            "connects to a Kubernetes API."
        ),
        log_level=resolved.log_level,
        host=resolved.mcp_host,
        port=resolved.mcp_port,
        streamable_http_path="/mcp",
        json_response=True,
    )

    register_inventory_tools(server, resolved_inventory)
    register_prometheus_tools(server, resolved_prometheus)
    register_knowledge_tools(server, resolved_skills, resolved_known_issues)
    register_health_tools(server, correlator)
    register_resources(server, resolved_skills)
    register_prompts(server)

    @server.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> Response:
        return JSONResponse(
            {
                "status": "ok",
                "server": resolved.mcp_server_name,
                "version": __version__,
                "prometheus_mode": resolved.prometheus_mode,
                "skills_loaded": len(resolved_skills.list_skills()),
            }
        )

    return server


settings = Settings()
mcp = create_server(settings)
app = mcp.streamable_http_app()
