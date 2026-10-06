import json
import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

import httpx

from kube_triage.config import Settings
from kube_triage.errors import PrometheusError, ValidationError
from kube_triage.models import (
    AlertRecord,
    MetricPoint,
    MetricQueryResult,
    MetricSeries,
    utc_now,
)


class ApprovedMetric(StrEnum):
    DESIRED_REPLICAS = "desired_replicas"
    AVAILABLE_REPLICAS = "available_replicas"
    RESTARTS_LAST_1H = "restarts_last_1h"
    CPU_USAGE_CORES = "cpu_usage_cores"
    MEMORY_WORKING_SET_BYTES = "memory_working_set_bytes"
    TARGET_UP = "target_up"


METRIC_CATALOG: dict[ApprovedMetric, dict[str, Any]] = {
    ApprovedMetric.DESIRED_REPLICAS: {
        "metric": "kube_deployment_spec_replicas",
        "description": "Desired deployment replicas.",
        "deployment_scoped": True,
    },
    ApprovedMetric.AVAILABLE_REPLICAS: {
        "metric": "kube_deployment_status_replicas_available",
        "description": "Available deployment replicas.",
        "deployment_scoped": True,
    },
    ApprovedMetric.RESTARTS_LAST_1H: {
        "metric": "deployment:pod_restarts:increase1h",
        "description": "Container restart increase over one hour.",
        "deployment_scoped": True,
    },
    ApprovedMetric.CPU_USAGE_CORES: {
        "metric": "deployment:container_cpu_usage:rate5m",
        "description": "Deployment CPU usage in cores over five minutes.",
        "deployment_scoped": True,
    },
    ApprovedMetric.MEMORY_WORKING_SET_BYTES: {
        "metric": "deployment:container_memory_working_set_bytes:sum",
        "description": "Deployment memory working set in bytes.",
        "deployment_scoped": True,
    },
    ApprovedMetric.TARGET_UP: {
        "metric": "up",
        "description": "Minimum scrape target availability for the cluster.",
        "deployment_scoped": False,
    },
}

_SAFE_LABEL = re.compile(r"^[A-Za-z0-9_.:-]+$")


class PrometheusClient(Protocol):
    async def query(
        self,
        metric: ApprovedMetric,
        cluster_name: str,
        namespace: str | None = None,
        deployment: str | None = None,
    ) -> MetricQueryResult: ...

    async def query_range(
        self,
        metric: ApprovedMetric,
        cluster_name: str,
        start: datetime,
        end: datetime,
        step_seconds: int,
        namespace: str | None = None,
        deployment: str | None = None,
    ) -> MetricQueryResult: ...

    async def get_firing_alerts(
        self,
        cluster_name: str,
        namespace: str | None = None,
        deployment: str | None = None,
    ) -> list[AlertRecord]: ...


def validate_range(
    start: datetime,
    end: datetime,
    step_seconds: int,
    *,
    max_range_hours: int,
    min_step_seconds: int,
) -> None:
    if start.tzinfo is None or end.tzinfo is None:
        raise ValidationError("timezone_required", "start and end must include a timezone")
    if end <= start:
        raise ValidationError("invalid_time_range", "end must be after start")
    if end - start > timedelta(hours=max_range_hours):
        raise ValidationError(
            "range_too_large",
            f"time range cannot exceed {max_range_hours} hours",
        )
    if step_seconds < min_step_seconds:
        raise ValidationError(
            "step_too_small",
            f"step_seconds must be at least {min_step_seconds}",
        )


def build_promql(
    metric: ApprovedMetric,
    cluster_label: str,
    cluster_name: str,
    namespace: str | None = None,
    deployment: str | None = None,
) -> str:
    values = [cluster_label, cluster_name]
    definition = METRIC_CATALOG[metric]
    if definition["deployment_scoped"]:
        if not namespace or not deployment:
            raise ValidationError(
                "deployment_scope_required",
                f"namespace and deployment are required for {metric.value}",
            )
        values.extend((namespace, deployment))
    if any(not _SAFE_LABEL.fullmatch(value) for value in values):
        raise ValidationError(
            "invalid_label",
            "cluster and Kubernetes label values may contain only letters, numbers, "
            "'.', '_', ':', or '-'",
        )

    selectors = [f'{cluster_label}="{cluster_name}"']
    if definition["deployment_scoped"]:
        selectors.extend((f'namespace="{namespace}"', f'deployment="{deployment}"'))
    joined = ",".join(selectors)
    prom_metric = definition["metric"]
    if metric == ApprovedMetric.TARGET_UP:
        return f"min({prom_metric}{{{joined}}})"
    return f"sum({prom_metric}{{{joined}}})"


class FixturePrometheusClient:
    def __init__(self, fixture_file: Path, settings: Settings) -> None:
        try:
            self._data = json.loads(fixture_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PrometheusError(
                "fixture_load_failed",
                f"Unable to load Prometheus fixture: {fixture_file}",
            ) from exc
        self._settings = settings

    async def query(
        self,
        metric: ApprovedMetric,
        cluster_name: str,
        namespace: str | None = None,
        deployment: str | None = None,
    ) -> MetricQueryResult:
        query = build_promql(
            metric,
            self._settings.prometheus_cluster_label,
            cluster_name,
            namespace,
            deployment,
        )
        cluster = self._cluster(cluster_name)
        if metric == ApprovedMetric.TARGET_UP:
            value = cluster.get("target_up")
            source: Mapping[str, Any] = cluster
        else:
            source = self._deployment(cluster, namespace, deployment)
            value = source.get("metrics", {}).get(metric.value)

        series: list[MetricSeries] = []
        if value is not None:
            observed_at = utc_now() - timedelta(
                seconds=float(source.get("observed_age_seconds", 0))
            )
            labels = {"cluster": cluster_name}
            if namespace and deployment:
                labels.update({"namespace": namespace, "deployment": deployment})
            series.append(
                MetricSeries(
                    labels=labels,
                    points=[MetricPoint(timestamp=observed_at, value=float(value))],
                )
            )
        return MetricQueryResult(
            metric=metric.value,
            query=query,
            cluster_name=cluster_name,
            series=series,
        )

    async def query_range(
        self,
        metric: ApprovedMetric,
        cluster_name: str,
        start: datetime,
        end: datetime,
        step_seconds: int,
        namespace: str | None = None,
        deployment: str | None = None,
    ) -> MetricQueryResult:
        validate_range(
            start,
            end,
            step_seconds,
            max_range_hours=self._settings.prometheus_max_range_hours,
            min_step_seconds=self._settings.prometheus_min_step_seconds,
        )
        query = build_promql(
            metric,
            self._settings.prometheus_cluster_label,
            cluster_name,
            namespace,
            deployment,
        )
        cluster = self._cluster(cluster_name)
        source = self._deployment(cluster, namespace, deployment)
        values = source.get("history", {}).get(metric.value, [])
        points: list[MetricPoint] = []
        if values:
            interval = (end - start) / max(len(values) - 1, 1)
            points = [
                MetricPoint(timestamp=start + interval * index, value=float(value))
                for index, value in enumerate(values)
            ]
        labels = {
            "cluster": cluster_name,
            "namespace": namespace or "",
            "deployment": deployment or "",
        }
        series = [MetricSeries(labels=labels, points=points)] if points else []
        return MetricQueryResult(
            metric=metric.value,
            query=query,
            cluster_name=cluster_name,
            series=series,
        )

    async def get_firing_alerts(
        self,
        cluster_name: str,
        namespace: str | None = None,
        deployment: str | None = None,
    ) -> list[AlertRecord]:
        cluster = self._cluster(cluster_name)
        alerts: list[AlertRecord] = []
        for item in cluster.get("alerts", []):
            if namespace and item.get("namespace") != namespace:
                continue
            if deployment and item.get("deployment") != deployment:
                continue
            alerts.append(
                AlertRecord(
                    cluster_name=cluster_name,
                    observed_at=utc_now()
                    - timedelta(seconds=float(item.get("observed_age_seconds", 0))),
                    **{key: value for key, value in item.items() if key != "observed_age_seconds"},
                )
            )
        return alerts

    def _cluster(self, cluster_name: str) -> Mapping[str, Any]:
        cluster = self._data.get("clusters", {}).get(cluster_name)
        if cluster is None:
            return {}
        return cluster

    @staticmethod
    def _deployment(
        cluster: Mapping[str, Any],
        namespace: str | None,
        deployment: str | None,
    ) -> Mapping[str, Any]:
        if not namespace or not deployment:
            return {}
        return cluster.get("deployments", {}).get(f"{namespace}/{deployment}", {})


class HttpPrometheusClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.prometheus_url:
            raise PrometheusError("missing_url", "PROMETHEUS_URL is required")
        self._settings = settings
        self._base_url = settings.prometheus_url.rstrip("/")

    async def query(
        self,
        metric: ApprovedMetric,
        cluster_name: str,
        namespace: str | None = None,
        deployment: str | None = None,
    ) -> MetricQueryResult:
        query = build_promql(
            metric,
            self._settings.prometheus_cluster_label,
            cluster_name,
            namespace,
            deployment,
        )
        payload = await self._request("/api/v1/query", {"query": query})
        return self._parse_result(metric, query, cluster_name, payload)

    async def query_range(
        self,
        metric: ApprovedMetric,
        cluster_name: str,
        start: datetime,
        end: datetime,
        step_seconds: int,
        namespace: str | None = None,
        deployment: str | None = None,
    ) -> MetricQueryResult:
        validate_range(
            start,
            end,
            step_seconds,
            max_range_hours=self._settings.prometheus_max_range_hours,
            min_step_seconds=self._settings.prometheus_min_step_seconds,
        )
        query = build_promql(
            metric,
            self._settings.prometheus_cluster_label,
            cluster_name,
            namespace,
            deployment,
        )
        payload = await self._request(
            "/api/v1/query_range",
            {
                "query": query,
                "start": start.astimezone(UTC).timestamp(),
                "end": end.astimezone(UTC).timestamp(),
                "step": step_seconds,
            },
        )
        return self._parse_result(metric, query, cluster_name, payload)

    async def get_firing_alerts(
        self,
        cluster_name: str,
        namespace: str | None = None,
        deployment: str | None = None,
    ) -> list[AlertRecord]:
        for value in (cluster_name, namespace, deployment):
            if value is not None and not _SAFE_LABEL.fullmatch(value):
                raise ValidationError("invalid_label", "alert label value is invalid")
        selectors = [
            'alertstate="firing"',
            f'{self._settings.prometheus_cluster_label}="{cluster_name}"',
        ]
        if namespace:
            selectors.append(f'namespace="{namespace}"')
        if deployment:
            selectors.append(f'deployment="{deployment}"')
        payload = await self._request(
            "/api/v1/query",
            {"query": f"ALERTS{{{','.join(selectors)}}}"},
        )
        alerts: list[AlertRecord] = []
        for item in payload.get("data", {}).get("result", []):
            labels = {str(key): str(value) for key, value in item.get("metric", {}).items()}
            timestamp = self._point(item.get("value", [utc_now().timestamp(), "1"])).timestamp
            severity = labels.get("severity", "warning").lower()
            if severity not in {"info", "warning", "critical"}:
                severity = "warning"
            alerts.append(
                AlertRecord(
                    cluster_name=cluster_name,
                    namespace=labels.get("namespace"),
                    deployment=labels.get("deployment"),
                    name=labels.get("alertname", "unknown"),
                    severity=severity,
                    summary=labels.get("summary", ""),
                    labels=labels,
                    observed_at=timestamp,
                )
            )
        return alerts

    async def _request(self, path: str, params: Mapping[str, Any]) -> dict[str, Any]:
        auth = None
        if self._settings.prometheus_username is not None:
            password = self._settings.prometheus_password
            auth = (
                self._settings.prometheus_username,
                password.get_secret_value() if password else "",
            )
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.prometheus_timeout_seconds,
                auth=auth,
            ) as client:
                response = await client.get(f"{self._base_url}{path}", params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PrometheusError(
                "request_failed",
                "Prometheus request failed",
                retryable=True,
            ) from exc
        if len(response.content) > self._settings.prometheus_max_response_bytes:
            raise PrometheusError("response_too_large", "Prometheus response exceeded the limit")
        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise PrometheusError("invalid_response", "Prometheus returned invalid JSON") from exc
        if payload.get("status") != "success":
            raise PrometheusError("query_failed", "Prometheus rejected the approved query")
        return payload

    @classmethod
    def _parse_result(
        cls,
        metric: ApprovedMetric,
        query: str,
        cluster_name: str,
        payload: Mapping[str, Any],
    ) -> MetricQueryResult:
        series: list[MetricSeries] = []
        for item in payload.get("data", {}).get("result", []):
            raw_points = item.get("values")
            if raw_points is None and "value" in item:
                raw_points = [item["value"]]
            points = [cls._point(value) for value in (raw_points or [])]
            labels = {str(key): str(value) for key, value in item.get("metric", {}).items()}
            series.append(MetricSeries(labels=labels, points=points))
        return MetricQueryResult(
            metric=metric.value,
            query=query,
            cluster_name=cluster_name,
            series=series,
        )

    @staticmethod
    def _point(value: list[Any]) -> MetricPoint:
        numeric = float(value[1])
        if not math.isfinite(numeric):
            raise PrometheusError("non_finite_value", "Prometheus returned a non-finite value")
        return MetricPoint(
            timestamp=datetime.fromtimestamp(float(value[0]), tz=UTC),
            value=numeric,
        )


def create_prometheus_client(settings: Settings) -> PrometheusClient:
    if settings.prometheus_mode == "fixture":
        return FixturePrometheusClient(settings.prometheus_fixture_file, settings)
    return HttpPrometheusClient(settings)