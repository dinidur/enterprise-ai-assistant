---
doc_id: "INC-PAY-0007"
title: "Incident Report: payment failures on payment-authorisation-api (2026-04-30)"
department: "payments"
document_type: "incident"
access_level: "internal"
created_date: "2026-04-30"
tags: ["payment", "outage", "incident", "connection-pool-exhaustion"]
---

# Incident Report: payment failures on payment-authorisation-api (2026-04-30)

## Summary

On 2026-04-30 the `payment-authorisation-api` service returned elevated payment
failures for 209 minutes. Approximately 19,365 customer payment
attempts failed during the window. Severity was classified as SEV3.

## Impact

- Failed payment authorisations: 19,365
- Customer-facing duration: 209 minutes
- Affected regions: EU-West

## Timeline

- T+0: Error rate on `payment-authorisation-api` crossed the 2% alert threshold.
- T+6m: On-call engineer paged and incident channel opened.
- T+22m: Root cause identified.
- T+209m: Service restored and error rate returned to baseline.

## Root Cause

**Connection pool exhaustion.** The payment service exhausted its database connection pool during a traffic spike, so new authorisation requests queued until they timed out.

## Remediation

Raise pool ceiling, add a bulkhead per downstream, alert at 80% saturation.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `payment-authorisation-api`.
- Track the fix in the payments reliability backlog.

