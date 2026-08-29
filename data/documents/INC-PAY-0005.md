---
doc_id: "INC-PAY-0005"
title: "Incident Report: payment failures on ledger-service (2026-02-22)"
department: "payments"
document_type: "incident"
access_level: "confidential"
created_date: "2026-02-22"
tags: ["payment", "outage", "incident", "connection-pool-exhaustion"]
---

# Incident Report: payment failures on ledger-service (2026-02-22)

## Summary

On 2026-02-22 the `ledger-service` service returned elevated payment
failures for 228 minutes. Approximately 22,941 customer payment
attempts failed during the window. Severity was classified as SEV1.

## Impact

- Failed payment authorisations: 22,941
- Customer-facing duration: 228 minutes
- Affected regions: AP-South

## Timeline

- T+0: Error rate on `ledger-service` crossed the 2% alert threshold.
- T+15m: On-call engineer paged and incident channel opened.
- T+18m: Root cause identified.
- T+228m: Service restored and error rate returned to baseline.

## Root Cause

**Connection pool exhaustion.** The payment service exhausted its database connection pool during a traffic spike, so new authorisation requests queued until they timed out.

## Remediation

Raise pool ceiling, add a bulkhead per downstream, alert at 80% saturation.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `ledger-service`.
- Track the fix in the payments reliability backlog.

