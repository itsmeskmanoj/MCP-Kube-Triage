import pytest
from sqlalchemy import event

from kube_triage.clients.inventory import InventoryRepository
from kube_triage.errors import ValidationError


def test_same_name_isolated_by_cluster(inventory: InventoryRepository) -> None:
    cluster_a = inventory.get_deployment("cluster-a", "payments", "payments-api")
    cluster_b = inventory.get_deployment("cluster-b", "payments", "payments-api")

    assert cluster_a is not None
    assert cluster_b is not None
    assert cluster_a.desired_replicas == 3
    assert cluster_b.desired_replicas == 2


def test_filters_are_combined(inventory: InventoryRepository) -> None:
    results = inventory.list_deployments(
        cluster_name="cluster-a",
        owner_team="payments",
    )

    assert [(item.namespace, item.deployment_name) for item in results] == [
        ("payments", "payments-api")
    ]


def test_query_path_executes_select_only(inventory: InventoryRepository) -> None:
    statements: list[str] = []

    def capture_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(inventory.engine, "before_cursor_execute", capture_statement)
    try:
        inventory.list_deployments(cluster_name="cluster-a")
        inventory.get_deployment("cluster-b", "payments", "payments-api")
    finally:
        event.remove(inventory.engine, "before_cursor_execute", capture_statement)

    assert statements
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)


def test_limit_is_bounded(inventory: InventoryRepository) -> None:
    with pytest.raises(ValidationError, match="limit must be between"):
        inventory.list_deployments(limit=1001)
