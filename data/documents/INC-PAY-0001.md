---
doc_id: "INC-PAY-0001"
title: "Incident Report: payment failures on payment-authorisation-api (2026-04-06)"
department: "payments"
document_type: "incident"
access_level: "confidential"
created_date: "2026-04-06"
tags: ["payment", "outage", "incident", "connection-pool-exhaustion"]
---

# Incident Report: payment failures on payment-authorisation-api (2026-04-06)

## Summary

On 2026-04-06 the `payment-authorisation-api` service returned elevated payment
failures for 74 minutes. Approximately 15,028 customer payment
attempts failed during the window. Severity was classified as SEV3.

## Impact

- Failed payment authorisations: 15,028
- Customer-facing duration: 74 minutes
- Affected regions: US-East

## Timeline

- T+0: Error rate on `payment-authorisation-api` crossed the 2% alert threshold.
- T+14m: On-call engineer paged and incident channel opened.
- T+22m: Root cause identified.
- T+74m: Service restored and error rate returned to baseline.

## Root Cause

**Connection pool exhaustion.** The payment service exhausted its database connection pool during a traffic spike, so new authorisation requests queued until they timed out.

## Remediation

Raise pool ceiling, add a bulkhead per downstream, alert at 80% saturation.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `payment-authorisation-api`.
- Track the fix in the payments reliability backlog.

