import asyncio
from datetime import UTC, datetime, timedelta

from kube_triage.clients.inventory import InventoryRepository
from kube_triage.clients.prometheus import ApprovedMetric, PrometheusClient
from kube_triage.config import Settings
from kube_triage.errors import OperationsError
from kube_triage.models import (
    AlertRecord,
    HealthAssessment,
    HealthStatus,
    MetricQueryResult,
    utc_now,
)
from kube_triage.skills.loader import SkillRegistry

_HEALTH_METRICS = (
    ApprovedMetric.DESIRED_REPLICAS,
    ApprovedMetric.AVAILABLE_REPLICAS,
    ApprovedMetric.RESTARTS_LAST_1H,
    ApprovedMetric.CPU_USAGE_CORES,
    ApprovedMetric.MEMORY_WORKING_SET_BYTES,
)


class HealthCorrelator:
    def __init__(
        self,
        inventory: InventoryRepository,
        prometheus: PrometheusClient,
        skills: SkillRegistry,
        settings: Settings,
    ) -> None:
        self._inventory = inventory
        self._prometheus = prometheus
        self._skills = skills
        self._settings = settings

    async def evaluate(
        self,
        cluster_name: str,
        namespace: str,
        deployment: str,
    ) -> HealthAssessment:
        record = self._inventory.get_deployment(cluster_name, namespace, deployment)
        if record is None:
            return HealthAssessment(
                cluster=cluster_name,
                namespace=namespace,
                deployment=deployment,
                status=HealthStatus.UNKNOWN,
                facts=[],
                hypotheses=[],
                matched_skills=[],
                missing_evidence=["deployment inventory record"],
            )

        requests = [
            self._prometheus.query(metric, cluster_name, namespace, deployment)
            for metric in _HEALTH_METRICS
        ]
        results = await asyncio.gather(
            *requests,
            self._prometheus.get_firing_alerts(cluster_name, namespace, deployment),
            return_exceptions=True,
        )

        facts = [
            f"inventory_desired_replicas={record.desired_replicas}",
            f"cpu_request_cores={record.cpu_request_cores:g}",
            f"memory_request_bytes={record.memory_request_bytes}",
        ]
        missing: list[str] = []
        hypotheses: list[str] = []
        signals: list[str] = []
        metric_values: dict[ApprovedMetric, float] = {}

        updated_at = self._as_utc(record.updated_at)
        if utc_now() - updated_at > timedelta(hours=self._settings.inventory_stale_after_hours):
            missing.append("fresh deployment inventory")

        for metric, result in zip(_HEALTH_METRICS, results[:-1], strict=True):
            if isinstance(result, BaseException):
                missing.append(f"{metric.value}: {self._error_code(result)}")
                continue
            value = self._latest_value(result)
            if value is None:
                missing.append(metric.value)
                continue
            numeric, observed_at = value
            facts.append(f"{metric.value}={numeric:g}")
            if utc_now() - observed_at > timedelta(
                seconds=self._settings.metric_stale_after_seconds
            ):
                missing.append(f"fresh {metric.value}")
                continue
            metric_values[metric] = numeric

        raw_alerts = results[-1]
        alerts: list[AlertRecord] = []
        if isinstance(raw_alerts, BaseException):
            missing.append(f"firing alerts: {self._error_code(raw_alerts)}")
        else:
            alerts = raw_alerts
            for alert in alerts:
                facts.append(f"firing_alert={alert.name}:{alert.severity}")
                signals.append(alert.name)

        desired = metric_values.get(ApprovedMetric.DESIRED_REPLICAS)
        available = metric_values.get(ApprovedMetric.AVAILABLE_REPLICAS)
        restarts = metric_values.get(ApprovedMetric.RESTARTS_LAST_1H)
        cpu = metric_values.get(ApprovedMetric.CPU_USAGE_CORES)
        memory = metric_values.get(ApprovedMetric.MEMORY_WORKING_SET_BYTES)

        critical = any(alert.severity == "critical" for alert in alerts)
        degraded = any(alert.severity == "warning" for alert in alerts)
        if desired is not None and available is not None:
            if desired > 0 and available <= 0:
                critical = True
                hypotheses.append("The deployment currently has no available replicas.")
                signals.extend(("deployment has unavailable replicas", "replica mismatch"))
            elif available < desired:
                degraded = True
                hypotheses.append("One or more replicas may be failing readiness or startup.")
                signals.extend(("deployment has unavailable replicas", "replica mismatch"))
            if desired != record.desired_replicas:
                degraded = True
                hypotheses.append("Inventory and live desired replica counts may have drifted.")
                signals.append("desired and available replicas do not match")

        if restarts is not None and restarts >= self._settings.health_restart_warning:
            degraded = True
            hypotheses.append("One or more containers may be restarting repeatedly.")
            signals.extend(("high container restarts", "pods keep restarting"))

        if cpu is not None:
            if record.cpu_request_cores <= 0:
                missing.append("positive CPU request")
            else:
                cpu_ratio = cpu / record.cpu_request_cores
                facts.append(f"cpu_request_ratio={cpu_ratio:.3f}")
                if cpu_ratio >= self._settings.health_cpu_warning_ratio:
                    degraded = True
                    hypotheses.append("CPU usage is near or above the configured request.")
                    signals.append("high cpu usage")

        if memory is not None:
            if record.memory_request_bytes <= 0:
                missing.append("positive memory request")
            else:
                memory_ratio = memory / record.memory_request_bytes
                facts.append(f"memory_request_ratio={memory_ratio:.3f}")
                if memory_ratio >= self._settings.health_memory_warning_ratio:
                    degraded = True
                    hypotheses.append("Memory working set is near or above the configured request.")
                    signals.append("high memory usage")

        if critical:
            status = HealthStatus.CRITICAL
        elif missing:
            status = HealthStatus.UNKNOWN
        elif degraded:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        matched = self._skills.search_many(signals, limit=2)
        return HealthAssessment(
            cluster=cluster_name,
            namespace=namespace,
            deployment=deployment,
            status=status,
            facts=facts,
            hypotheses=list(dict.fromkeys(hypotheses)),
            matched_skills=[skill.metadata.id for skill in matched],
            missing_evidence=list(dict.fromkeys(missing)),
            alerts=alerts,
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @classmethod
    def _latest_value(cls, result: MetricQueryResult) -> tuple[float, datetime] | None:
        points = [point for series in result.series for point in series.points]
        if not points:
            return None
        latest = max(points, key=lambda point: point.timestamp)
        return latest.value, cls._as_utc(latest.timestamp)

    @staticmethod
    def _error_code(error: BaseException) -> str:
        if isinstance(error, OperationsError):
            return error.code
        return "unexpected_error"
