---
name: crashloopbackoff
id: deployment/crashloopbackoff
category: deployment
description: Diagnose containers repeatedly failing during startup or runtime
difficulty: intermediate
tags: [kubernetes, pods, containers, startup, restart]
tools_required: [get_deployment, prom_query, get_firing_alerts]
codes: [CrashLoopBackOff]
triggers:
  - pods keep restarting
  - container repeatedly fails to start
tier: core
est_tokens: 760
---

# CrashLoopBackOff

## Use When

A container repeatedly exits and Kubernetes is delaying subsequent starts.

## Do Not Use When

The pod has never been scheduled or no container has started.

## Safety Contract

All commands are display-only. The operator chooses and verifies `<context>` before running them locally.

## Distinguishing Evidence

Look for increasing restart counters, recent termination reasons, exit codes, and startup probe failures.

## Investigation

1. Confirm inventory and recent restart evidence with MCP tools.
2. Inspect pod status locally: `kubectl --context <context> -n <namespace> get pods -l app=<deployment> -o wide`.
3. Review events: `kubectl --context <context> -n <namespace> describe pod <pod>`.
4. Read prior-container logs: `kubectl --context <context> -n <namespace> logs <pod> -c <container> --previous --tail=200`.

## Root Cause

Common causes include invalid configuration, dependency failures, probe errors, resource limits, and application crashes.

## Operator-Owned Remediation

An authorized operator corrects the validated cause through the normal deployment process. The MCP server performs no action.

## Verification

Confirm restart growth stops, readiness succeeds, and available replicas return to desired.

## Prevention

Validate configuration before rollout, use meaningful startup probes, and alert on restart increases.
