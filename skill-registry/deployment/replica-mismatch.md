---
name: replica-mismatch
id: deployment/replica-mismatch
category: deployment
description: Diagnose a deployment with fewer available replicas than desired
difficulty: beginner
tags: [kubernetes, deployment, replicas, unavailable]
tools_required: [get_deployment, prom_query, get_firing_alerts]
codes: [KubeDeploymentReplicasMismatch]
triggers:
  - deployment has unavailable replicas
  - desired and available replicas do not match
tier: core
est_tokens: 700
---

# Deployment Replica Mismatch

## Use When

Available deployment replicas remain below desired replicas.

## Do Not Use When

The deployment is intentionally scaled to zero or metric data is stale.

## Safety Contract

The MCP server only returns evidence and display-only checks. The operator runs commands after verifying `<context>`.

## Distinguishing Evidence

Compare inventory desired replicas, live desired and available metrics, restarts, alerts, and rollout conditions.

## Investigation

1. Confirm inventory and metric timestamps.
2. View deployment conditions: `kubectl --context <context> -n <namespace> get deployment <deployment> -o yaml`.
3. List owned pods: `kubectl --context <context> -n <namespace> get pods -l app=<deployment> -o wide`.
4. Review events: `kubectl --context <context> -n <namespace> describe deployment <deployment>`.

## Root Cause

Possible causes include pending pods, readiness failures, image pulls, crashes, rollout constraints, or stale label correlation.

## Operator-Owned Remediation

Only an authorized operator chooses and applies remediation after the failing condition is confirmed.

## Verification

Available replicas must equal desired replicas and the mismatch alert must clear.

## Prevention

Alert on sustained mismatch and keep deployment-to-pod recording rules validated.
