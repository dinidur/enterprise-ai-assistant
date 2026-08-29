---
doc_id: "INC-PAY-0018"
title: "Incident Report: payment failures on payment-authorisation-api (2026-03-12)"
department: "payments"
document_type: "incident"
access_level: "internal"
created_date: "2026-03-12"
tags: ["payment", "outage", "incident", "schema-migration-lock"]
---

# Incident Report: payment failures on payment-authorisation-api (2026-03-12)

## Summary

On 2026-03-12 the `payment-authorisation-api` service returned elevated payment
failures for 137 minutes. Approximately 1,676 customer payment
attempts failed during the window. Severity was classified as SEV3.

## Impact

- Failed payment authorisations: 1,676
- Customer-facing duration: 137 minutes
- Affected regions: EU-West

## Timeline

- T+0: Error rate on `payment-authorisation-api` crossed the 2% alert threshold.
- T+8m: On-call engineer paged and incident channel opened.
- T+35m: Root cause identified.
- T+137m: Service restored and error rate returned to baseline.

## Root Cause

**Schema migration lock.** An online migration held an exclusive lock on the transactions table, blocking writes from the authorisation path.

## Remediation

Use non-blocking migrations and run them outside the peak window.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `payment-authorisation-api`.
- Track the fix in the payments reliability backlog.

