---
doc_id: "INC-PAY-0002"
title: "Incident Report: payment failures on payment-authorisation-api (2026-01-20)"
department: "payments"
document_type: "incident"
access_level: "confidential"
created_date: "2026-01-20"
tags: ["payment", "outage", "incident", "schema-migration-lock"]
---

# Incident Report: payment failures on payment-authorisation-api (2026-01-20)

## Summary

On 2026-01-20 the `payment-authorisation-api` service returned elevated payment
failures for 20 minutes. Approximately 2,352 customer payment
attempts failed during the window. Severity was classified as SEV3.

## Impact

- Failed payment authorisations: 2,352
- Customer-facing duration: 20 minutes
- Affected regions: EU-West

## Timeline

- T+0: Error rate on `payment-authorisation-api` crossed the 2% alert threshold.
- T+6m: On-call engineer paged and incident channel opened.
- T+30m: Root cause identified.
- T+20m: Service restored and error rate returned to baseline.

## Root Cause

**Schema migration lock.** An online migration held an exclusive lock on the transactions table, blocking writes from the authorisation path.

## Remediation

Use non-blocking migrations and run them outside the peak window.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `payment-authorisation-api`.
- Track the fix in the payments reliability backlog.

