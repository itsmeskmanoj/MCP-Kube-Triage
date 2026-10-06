from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class ErrorComponent(StrEnum):
    VALIDATION = "validation"
    DATABASE = "database"
    PROMETHEUS = "prometheus"
    KNOWLEDGE = "knowledge"
    CORRELATION = "correlation"


class ErrorDetail(BaseModel):
    component: ErrorComponent
    code: str
    message: str
    retryable: bool = False


class ToolResultEnvelope(BaseModel):
    ok: bool
    data: dict[str, Any] | None = None
    error: ErrorDetail | None = None
    observed_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def success(cls, data: dict[str, Any]) -> "ToolResultEnvelope":
        return cls(ok=True, data=data)

    @classmethod
    def failure(
        cls,
        component: ErrorComponent,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> "ToolResultEnvelope":
        return cls(
            ok=False,
            error=ErrorDetail(
                component=component,
                code=code,
                message=message,
                retryable=retryable,
            ),
        )


class DeploymentRecord(BaseModel):
    id: int
    cluster_name: str
    namespace: str
    deployment_name: str
    application_name: str
    environment: str
    owner_team: str
    image: str
    desired_replicas: int = Field(ge=0)
    cpu_request_cores: float = Field(ge=0)
    memory_request_bytes: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class MetricPoint(BaseModel):
    timestamp: datetime
    value: float


class MetricSeries(BaseModel):
    labels: dict[str, str]
    points: list[MetricPoint]


class MetricQueryResult(BaseModel):
    metric: str
    query: str
    cluster_name: str
    series: list[MetricSeries]
    observed_at: datetime = Field(default_factory=utc_now)


class AlertRecord(BaseModel):
    cluster_name: str
    namespace: str | None = None
    deployment: str | None = None
    name: str
    severity: Literal["info", "warning", "critical"]
    summary: str = ""
    labels: dict[str, str] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=utc_now)


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class HealthAssessment(BaseModel):
    cluster: str
    namespace: str
    deployment: str
    status: HealthStatus
    facts: list[str]
    hypotheses: list[str]
    matched_skills: list[str]
    missing_evidence: list[str]
    alerts: list[AlertRecord] = Field(default_factory=list)
    observed_at: datetime = Field(default_factory=utc_now)


class SkillSummary(BaseModel):
    id: str
    name: str
    category: str
    description: str
    difficulty: str
    tags: list[str]
    codes: list[str]
    triggers: list[str]
    tier: str
    est_tokens: int = Field(ge=1)
    uri: str


class KnownIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    signals: list[str]
    skill_id: str
    status: Literal["active", "monitoring", "resolved"]
    summary: str
