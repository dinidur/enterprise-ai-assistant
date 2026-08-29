---
doc_id: "INC-PAY-0014"
title: "Incident Report: payment failures on settlement-worker (2026-01-20)"
department: "payments"
document_type: "incident"
access_level: "internal"
created_date: "2026-01-20"
tags: ["payment", "outage", "incident", "third-party-gateway-timeout"]
---

# Incident Report: payment failures on settlement-worker (2026-01-20)

## Summary

On 2026-01-20 the `settlement-worker` service returned elevated payment
failures for 164 minutes. Approximately 4,563 customer payment
attempts failed during the window. Severity was classified as SEV3.

## Impact

- Failed payment authorisations: 4,563
- Customer-facing duration: 164 minutes
- Affected regions: all regions

## Timeline

- T+0: Error rate on `settlement-worker` crossed the 2% alert threshold.
- T+9m: On-call engineer paged and incident channel opened.
- T+54m: Root cause identified.
- T+164m: Service restored and error rate returned to baseline.

## Root Cause

**Third-party gateway timeout.** The upstream card gateway exceeded its p99 latency budget and our client had no circuit breaker, so slow calls consumed all worker threads.

## Remediation

Add a circuit breaker and a 3s hard timeout on gateway calls.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `settlement-worker`.
- Track the fix in the payments reliability backlog.

