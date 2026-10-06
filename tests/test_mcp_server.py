import pytest
from mcp.client.session import ClientSession

pytestmark = pytest.mark.anyio

EXPECTED_TOOLS = {
    "deployment_health",
    "get_deployment",
    "get_firing_alerts",
    "get_skill_index",
    "list_deployments",
    "prom_query",
    "prom_query_range",
    "read_skill",
    "search_skills",
}

EXPECTED_PROMPTS = {
    "cluster_health_summary",
    "deployment_health_check",
    "investigate_deployment",
    "investigate_unknown_issue",
}


async def test_discovery_lists_complete_surface(client_session: ClientSession) -> None:
    tools = await client_session.list_tools()
    resources = await client_session.list_resources()
    prompts = await client_session.list_prompts()

    assert {tool.name for tool in tools.tools} == EXPECTED_TOOLS
    assert len(resources.resources) == 9
    assert {prompt.name for prompt in prompts.prompts} == EXPECTED_PROMPTS
    uris = {str(resource.uri) for resource in resources.resources}
    assert "policy://kube-triage/read-only" in uris
    assert "catalog://kube-triage/metrics" in uris
    assert len([uri for uri in uris if uri.startswith("skill://")]) == 6


async def test_protocol_tool_calls_preserve_cluster(client_session: ClientSession) -> None:
    deployment = await client_session.call_tool(
        "get_deployment",
        {
            "cluster_name": "cluster-b",
            "namespace": "payments",
            "deployment_name": "payments-api",
        },
    )
    health = await client_session.call_tool(
        "deployment_health",
        {
            "cluster_name": "cluster-b",
            "namespace": "payments",
            "deployment": "payments-api",
        },
    )

    assert deployment.isError is False
    assert deployment.structuredContent["data"]["deployment"]["desired_replicas"] == 2
    assert health.isError is False
    assert health.structuredContent["data"]["health"]["status"] == "healthy"


async def test_protocol_errors_are_structured(client_session: ClientSession) -> None:
    result = await client_session.call_tool(
        "get_deployment",
        {
            "cluster_name": "cluster-a",
            "namespace": "missing",
            "deployment_name": "missing",
        },
    )

    assert result.isError is False
    assert result.structuredContent["ok"] is False
    assert result.structuredContent["error"]["component"] == "database"
    assert result.structuredContent["error"]["code"] == "deployment_not_found"


async def test_resources_and_prompts_render(client_session: ClientSession) -> None:
    resource = await client_session.read_resource("policy://kube-triage/read-only")
    prompt = await client_session.get_prompt(
        "deployment_health_check",
        {
            "cluster": "cluster-a",
            "namespace": "payments",
            "deployment": "payments-api",
        },
    )

    assert "never executes commands" in resource.contents[0].text.lower()
    assert "deployment_health" in prompt.messages[0].content.text
    assert "--context <context>" in prompt.messages[0].content.text
