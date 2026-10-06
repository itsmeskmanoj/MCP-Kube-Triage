from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from kube_triage.clients.inventory import (
    InventoryRepository,
    deployments_table,
    metadata,
)
from kube_triage.clients.prometheus import PrometheusClient, create_prometheus_client
from kube_triage.config import Settings
from kube_triage.health import HealthCorrelator
from kube_triage.known_issues.loader import KnownIssueRegistry
from kube_triage.server import create_server
from kube_triage.skills.loader import SkillRegistry

ROOT = Path(__file__).parents[1]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{(tmp_path / 'inventory.db').as_posix()}",
        prometheus_fixture_file=ROOT / "fixtures/prometheus.json",
        skill_registry_dir=ROOT / "skill-registry",
        known_issues_file=ROOT / "known-issues/catalog.yaml",
    )


@pytest.fixture
def inventory(settings: Settings) -> Iterator[InventoryRepository]:
    repository = InventoryRepository(
        settings.database_url,
        max_rows=settings.inventory_max_rows,
    )
    metadata.create_all(repository.engine)
    now = datetime.now(UTC)
    records = [
        {
            "id": 1,
            "cluster_name": "cluster-a",
            "namespace": "payments",
            "deployment_name": "payments-api",
            "application_name": "payments",
            "environment": "prod",
            "owner_team": "payments",
            "image": "payments-api:1.8.2",
            "desired_replicas": 3,
            "cpu_request_cores": 0.75,
            "memory_request_bytes": 805306368,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": 2,
            "cluster_name": "cluster-b",
            "namespace": "payments",
            "deployment_name": "payments-api",
            "application_name": "payments",
            "environment": "prod",
            "owner_team": "payments",
            "image": "payments-api:1.8.2",
            "desired_replicas": 2,
            "cpu_request_cores": 0.5,
            "memory_request_bytes": 536870912,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": 3,
            "cluster_name": "cluster-a",
            "namespace": "checkout",
            "deployment_name": "checkout-api",
            "application_name": "checkout",
            "environment": "prod",
            "owner_team": "checkout",
            "image": "checkout-api:4.2.0",
            "desired_replicas": 2,
            "cpu_request_cores": 0.5,
            "memory_request_bytes": 536870912,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": 4,
            "cluster_name": "cluster-a",
            "namespace": "platform",
            "deployment_name": "event-consumer",
            "application_name": "events",
            "environment": "prod",
            "owner_team": "platform",
            "image": "event-consumer:2.3.1",
            "desired_replicas": 2,
            "cpu_request_cores": 0.4,
            "memory_request_bytes": 402653184,
            "created_at": now,
            "updated_at": now,
        },
    ]
    with repository.engine.begin() as connection:
        connection.execute(deployments_table.insert(), records)
    yield repository
    repository.engine.dispose()


@pytest.fixture
def prometheus(settings: Settings) -> PrometheusClient:
    return create_prometheus_client(settings)


@pytest.fixture
def skills(settings: Settings) -> SkillRegistry:
    return SkillRegistry.load(settings.skill_registry_dir)


@pytest.fixture
def known_issues(settings: Settings, skills: SkillRegistry) -> KnownIssueRegistry:
    return KnownIssueRegistry.load(settings.known_issues_file, skills)


@pytest.fixture
def correlator(
    inventory: InventoryRepository,
    prometheus: PrometheusClient,
    skills: SkillRegistry,
    settings: Settings,
) -> HealthCorrelator:
    return HealthCorrelator(inventory, prometheus, skills, settings)


@pytest.fixture
def server(
    settings: Settings,
    inventory: InventoryRepository,
    prometheus: PrometheusClient,
    skills: SkillRegistry,
    known_issues: KnownIssueRegistry,
) -> FastMCP:
    return create_server(
        settings,
        inventory=inventory,
        prometheus=prometheus,
        skills=skills,
        known_issues=known_issues,
    )


@pytest.fixture
async def client_session(server: FastMCP) -> AsyncIterator[ClientSession]:
    async with create_connected_server_and_client_session(
        server,
        raise_exceptions=True,
    ) as session:
        yield session
