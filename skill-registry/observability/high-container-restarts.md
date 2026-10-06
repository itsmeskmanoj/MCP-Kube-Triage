---
name: high-container-restarts
id: observability/high-container-restarts
category: observability
description: Investigate a recent increase in pod container restart counters
difficulty: intermediate
tags: [kubernetes, prometheus, containers, restarts, reliability]
tools_required: [prom_query, prom_query_range, get_firing_alerts]
codes: [KubePodContainerStatusRestarts]
triggers:
  - high container restarts
  - restart count increased recently
tier: core
est_tokens: 720
---

# High Container Restarts

## Use When

The normalized one-hour restart increase is elevated for a deployment.

## Do Not Use When

The counter is old and no recent increase exists.

## Safety Contract

MCP queries are read-only. Any displayed command runs only in the operator's local CLI with explicit `<context>`.

## Distinguishing Evidence

Use a bounded timeline to determine when restart growth began and correlate it with alerts and rollout state.

## Investigation

1. Query the restart increase and recent range through approved MCP metrics.
2. Inspect pod status: `kubectl --context <context> -n <namespace> get pods -l app=<deployment>`.
3. Inspect termination state: `kubectl --context <context> -n <namespace> get pod <pod> -o jsonpath='{.status.containerStatuses}'`.

## Root Cause

Exit reason, exit code, events, and prior logs are required before assigning a cause.

## Operator-Owned Remediation

Application, configuration, probe, or resource changes remain operator-owned and follow deployment controls.

## Verification

Restart increase remains at zero or its expected baseline while all replicas stay available.

## Prevention

Use restart-rate alerts and preserve prior-container logs long enough for investigation.
