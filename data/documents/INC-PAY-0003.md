---
doc_id: "INC-PAY-0003"
title: "Incident Report: payment failures on payment-authorisation-api (2026-05-15)"
department: "payments"
document_type: "incident"
access_level: "confidential"
created_date: "2026-05-15"
tags: ["payment", "outage", "incident", "schema-migration-lock"]
---

# Incident Report: payment failures on payment-authorisation-api (2026-05-15)

## Summary

On 2026-05-15 the `payment-authorisation-api` service returned elevated payment
failures for 195 minutes. Approximately 42,990 customer payment
attempts failed during the window. Severity was classified as SEV3.

## Impact

- Failed payment authorisations: 42,990
- Customer-facing duration: 195 minutes
- Affected regions: all regions

## Timeline

- T+0: Error rate on `payment-authorisation-api` crossed the 2% alert threshold.
- T+6m: On-call engineer paged and incident channel opened.
- T+44m: Root cause identified.
- T+195m: Service restored and error rate returned to baseline.

## Root Cause

**Schema migration lock.** An online migration held an exclusive lock on the transactions table, blocking writes from the authorisation path.

## Remediation

Use non-blocking migrations and run them outside the peak window.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `payment-authorisation-api`.
- Track the fix in the payments reliability backlog.

