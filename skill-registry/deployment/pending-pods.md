---
name: pending-pods
id: deployment/pending-pods
category: deployment
description: Diagnose pods that remain pending before container startup
difficulty: beginner
tags: [kubernetes, pods, scheduling, capacity, pending]
tools_required: [get_deployment, get_firing_alerts]
codes: [FailedScheduling, Pending]
triggers:
  - pods are stuck pending
  - deployment pods cannot be scheduled
tier: core
est_tokens: 680
---

# Pending Pods

## Use When

One or more deployment pods remain in the Pending phase and available replicas are low.

## Do Not Use When

Containers have started and are repeatedly exiting; use the restart procedure instead.

## Safety Contract

Commands are guidance for the user's authenticated CLI and always require explicit `<context>` review.

## Distinguishing Evidence

Scheduling events identify resource scarcity, node selectors, affinity, taints, quotas, or unbound volumes.

## Investigation

1. Confirm the affected cluster, namespace, deployment, and desired replicas.
2. List pending pods: `kubectl --context <context> -n <namespace> get pods --field-selector=status.phase=Pending -o wide`.
3. Read scheduling events: `kubectl --context <context> -n <namespace> describe pod <pod>`.
4. Review namespace events: `kubectl --context <context> -n <namespace> get events --sort-by=.lastTimestamp`.

## Root Cause

Treat the scheduler's current event as evidence; do not infer capacity or policy failures without it.

## Operator-Owned Remediation

Capacity, requests, placement policy, quota, or storage changes require an authorized operator and normal change controls.

## Verification

Confirm pods are scheduled, become Ready, and available replicas reach desired.

## Prevention

Track scheduling latency, validate placement constraints, and maintain capacity headroom.
