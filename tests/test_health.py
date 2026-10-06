import pytest

from kube_triage.health import HealthCorrelator
from kube_triage.models import HealthStatus


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("cluster", "namespace", "deployment", "expected"),
    [
        ("cluster-a", "payments", "payments-api", HealthStatus.DEGRADED),
        ("cluster-a", "checkout", "checkout-api", HealthStatus.CRITICAL),
        ("cluster-a", "platform", "event-consumer", HealthStatus.UNKNOWN),
        ("cluster-b", "payments", "payments-api", HealthStatus.HEALTHY),
    ],
)
async def test_health_states(
    correlator: HealthCorrelator,
    cluster: str,
    namespace: str,
    deployment: str,
    expected: HealthStatus,
) -> None:
    result = await correlator.evaluate(cluster, namespace, deployment)

    assert result.status == expected
    if expected == HealthStatus.UNKNOWN:
        assert result.missing_evidence
    if expected in {HealthStatus.DEGRADED, HealthStatus.CRITICAL}:
        assert "deployment/replica-mismatch" in result.matched_skills


@pytest.mark.anyio
async def test_missing_inventory_is_unknown(correlator: HealthCorrelator) -> None:
    result = await correlator.evaluate("cluster-a", "missing", "missing")

    assert result.status == HealthStatus.UNKNOWN
    assert result.missing_evidence == ["deployment inventory record"]