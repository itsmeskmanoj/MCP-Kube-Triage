---
name: prometheus-target-down
id: observability/prometheus-target-down
category: observability
description: Diagnose missing deployment evidence caused by failed scrape targets
difficulty: intermediate
tags: [kubernetes, prometheus, scrape, targets, missing-metrics]
tools_required: [prom_query, get_firing_alerts]
codes: [TargetDown, PrometheusTargetMissing]
triggers:
  - prometheus target is down
  - deployment metrics are missing
tier: core
est_tokens: 710
---

# Prometheus Target Down

## Use When

Inventory exists but approved deployment metrics are absent or a target-down alert is firing.

## Do Not Use When

Only one normalized deployment label is absent while raw scrape targets remain healthy; verify recording-rule correlation first.

## Safety Contract

The MCP server reads Prometheus only and cannot alter scrape configuration. CLI checks remain local and context-explicit.

## Distinguishing Evidence

Separate endpoint availability, service discovery, scrape failure, and recording-rule label mismatch.

## Investigation

1. Query the approved `target_up` metric for the selected cluster.
2. Review firing target or rule alerts.
3. Inspect monitoring workloads locally: `kubectl --context <context> -n <monitoring-namespace> get pods -o wide`.
4. Inspect service endpoints: `kubectl --context <context> -n <namespace> get endpoints -o wide`.

## Root Cause

Do not equate missing normalized series with an application outage; validate scrape and rule stages separately.

## Operator-Owned Remediation

Monitoring configuration or rule changes are performed only by authorized observability operators.

## Verification

Targets report up, normalized series carry cluster/namespace/deployment labels, and data timestamps are fresh.

## Prevention

Continuously test recording rules and alert on both scrape failures and absent expected series.
