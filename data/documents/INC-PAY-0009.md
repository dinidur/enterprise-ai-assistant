---
doc_id: "INC-PAY-0009"
title: "Incident Report: payment failures on settlement-worker (2026-04-21)"
department: "payments"
document_type: "incident"
access_level: "confidential"
created_date: "2026-04-21"
tags: ["payment", "outage", "incident", "connection-pool-exhaustion"]
---

# Incident Report: payment failures on settlement-worker (2026-04-21)

## Summary

On 2026-04-21 the `settlement-worker` service returned elevated payment
failures for 53 minutes. Approximately 30,694 customer payment
attempts failed during the window. Severity was classified as SEV3.

## Impact

- Failed payment authorisations: 30,694
- Customer-facing duration: 53 minutes
- Affected regions: all regions

## Timeline

- T+0: Error rate on `settlement-worker` crossed the 2% alert threshold.
- T+7m: On-call engineer paged and incident channel opened.
- T+56m: Root cause identified.
- T+53m: Service restored and error rate returned to baseline.

## Root Cause

**Connection pool exhaustion.** The payment service exhausted its database connection pool during a traffic spike, so new authorisation requests queued until they timed out.

## Remediation

Raise pool ceiling, add a bulkhead per downstream, alert at 80% saturation.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `settlement-worker`.
- Track the fix in the payments reliability backlog.

