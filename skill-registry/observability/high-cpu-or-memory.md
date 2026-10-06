---
name: high-cpu-or-memory
id: observability/high-cpu-or-memory
category: observability
description: Compare deployment CPU or memory usage with configured requests
difficulty: intermediate
tags: [kubernetes, prometheus, cpu, memory, resources]
tools_required: [get_deployment, prom_query, prom_query_range]
codes: [CPUThrottlingHigh, ContainerMemoryNearLimit]
triggers:
  - high cpu usage
  - high memory usage
tier: core
est_tokens: 740
---

# High CPU or Memory

## Use When

CPU or memory usage approaches or exceeds the request recorded for a deployment.

## Do Not Use When

Requests are missing, zero, stale, or represent a different aggregation than the usage recording rule.

## Safety Contract

The server evaluates evidence only. Operators review `<context>` and run any CLI check locally.

## Distinguishing Evidence

Compare current ratios with a bounded timeline and determine whether the signal is sustained, periodic, or rollout-related.

## Investigation

1. Confirm requests in inventory and timestamps in metric results.
2. Query CPU and memory ranges with a step appropriate to the selected window.
3. Inspect declared resources: `kubectl --context <context> -n <namespace> get deployment <deployment> -o jsonpath='{.spec.template.spec.containers[*].resources}'`.

## Root Cause

Load growth, leaks, inefficient work, request sizing, and sidecars are hypotheses until per-container evidence supports them.

## Operator-Owned Remediation

Performance fixes or resource changes require capacity review, authorization, and the normal rollout process.

## Verification

Usage returns to the expected range without reducing availability or increasing restarts.

## Prevention

Review requests against historical percentiles and alert on sustained resource pressure.
