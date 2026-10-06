from datetime import UTC, datetime, timedelta

import pytest

from kube_triage.clients.prometheus import ApprovedMetric, PrometheusClient
from kube_triage.errors import ValidationError


@pytest.mark.anyio
async def test_fixture_instant_query_is_cluster_scoped(
    prometheus: PrometheusClient,
) -> None:
    cluster_a = await prometheus.query(
        ApprovedMetric.DESIRED_REPLICAS,
        "cluster-a",
        "payments",
        "payments-api",
    )
    cluster_b = await prometheus.query(
        ApprovedMetric.DESIRED_REPLICAS,
        "cluster-b",
        "payments",
        "payments-api",
    )

    assert cluster_a.series[0].points[0].value == 3
    assert cluster_b.series[0].points[0].value == 2
    assert 'cluster="cluster-a"' in cluster_a.query


@pytest.mark.anyio
async def test_range_query_is_bounded(prometheus: PrometheusClient) -> None:
    end = datetime.now(UTC)
    with pytest.raises(ValidationError, match="cannot exceed"):
        await prometheus.query_range(
            ApprovedMetric.CPU_USAGE_CORES,
            "cluster-a",
            end - timedelta(hours=25),
            end,
            60,
            "payments",
            "payments-api",
        )


@pytest.mark.anyio
async def test_range_query_returns_fixture_history(prometheus: PrometheusClient) -> None:
    end = datetime.now(UTC)
    result = await prometheus.query_range(
        ApprovedMetric.RESTARTS_LAST_1H,
        "cluster-a",
        end - timedelta(hours=1),
        end,
        60,
        "payments",
        "payments-api",
    )

    assert [point.value for point in result.series[0].points] == [0, 1, 2, 4, 7]


@pytest.mark.anyio
async def test_label_injection_is_rejected(prometheus: PrometheusClient) -> None:
    with pytest.raises(ValidationError, match="label values"):
        await prometheus.query(
            ApprovedMetric.DESIRED_REPLICAS,
            'cluster-a"}',
            "payments",
            "payments-api",
        )
