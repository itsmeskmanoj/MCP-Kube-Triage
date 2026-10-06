from collections.abc import Mapping
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    and_,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.exc import SQLAlchemyError

from kube_triage.errors import DatabaseError, ValidationError
from kube_triage.models import DeploymentRecord

metadata = MetaData()

deployments_table = Table(
    "deployments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("cluster_name", String(255), nullable=False),
    Column("namespace", String(255), nullable=False),
    Column("deployment_name", String(255), nullable=False),
    Column("application_name", String(255), nullable=False),
    Column("environment", String(64), nullable=False),
    Column("owner_team", String(255), nullable=False),
    Column("image", String(1024), nullable=False),
    Column("desired_replicas", Integer, nullable=False),
    Column("cpu_request_cores", Float, nullable=False),
    Column("memory_request_bytes", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "cluster_name",
        "namespace",
        "deployment_name",
        name="uq_deployment_target",
    ),
)


class InventoryRepository:
    """Read deployment inventory through parameterized SELECT statements only."""

    def __init__(self, database_url: str, *, max_rows: int = 200) -> None:
        self._engine: Engine = create_engine(database_url, pool_pre_ping=True)
        self._max_rows = max_rows

    @property
    def engine(self) -> Engine:
        return self._engine

    def list_deployments(
        self,
        *,
        cluster_name: str | None = None,
        namespace: str | None = None,
        owner_team: str | None = None,
        application_name: str | None = None,
        limit: int = 100,
    ) -> list[DeploymentRecord]:
        if limit < 1 or limit > self._max_rows:
            raise ValidationError(
                "invalid_limit",
                f"limit must be between 1 and {self._max_rows}",
            )

        filters = []
        for column, value in (
            (deployments_table.c.cluster_name, cluster_name),
            (deployments_table.c.namespace, namespace),
            (deployments_table.c.owner_team, owner_team),
            (deployments_table.c.application_name, application_name),
        ):
            if value is not None:
                filters.append(column == value)

        statement = select(deployments_table).order_by(
            deployments_table.c.cluster_name,
            deployments_table.c.namespace,
            deployments_table.c.deployment_name,
        )
        if filters:
            statement = statement.where(and_(*filters))
        statement = statement.limit(limit)

        try:
            with self._engine.connect() as connection:
                rows = connection.execute(statement).mappings().all()
        except SQLAlchemyError as exc:
            raise DatabaseError(
                "inventory_query_failed",
                "Deployment inventory query failed",
                retryable=True,
            ) from exc
        return [self._to_record(row) for row in rows]

    def get_deployment(
        self,
        cluster_name: str,
        namespace: str,
        deployment_name: str,
    ) -> DeploymentRecord | None:
        statement = select(deployments_table).where(
            deployments_table.c.cluster_name == cluster_name,
            deployments_table.c.namespace == namespace,
            deployments_table.c.deployment_name == deployment_name,
        )
        try:
            with self._engine.connect() as connection:
                row = connection.execute(statement).mappings().one_or_none()
        except SQLAlchemyError as exc:
            raise DatabaseError(
                "inventory_query_failed",
                "Deployment inventory query failed",
                retryable=True,
            ) from exc
        return self._to_record(row) if row is not None else None

    def check_connection(self) -> bool:
        try:
            with self._engine.connect() as connection:
                connection.execute(select(1)).scalar_one()
        except SQLAlchemyError as exc:
            raise DatabaseError(
                "inventory_unavailable",
                "Deployment inventory is unavailable",
                retryable=True,
            ) from exc
        return True

    @staticmethod
    def _to_record(row: RowMapping | Mapping[str, Any]) -> DeploymentRecord:
        return DeploymentRecord.model_validate(dict(row))
