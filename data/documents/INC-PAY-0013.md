---
doc_id: "INC-PAY-0013"
title: "Incident Report: payment failures on ledger-service (2026-05-04)"
department: "payments"
document_type: "incident"
access_level: "internal"
created_date: "2026-05-04"
tags: ["payment", "outage", "incident", "schema-migration-lock"]
---

# Incident Report: payment failures on ledger-service (2026-05-04)

## Summary

On 2026-05-04 the `ledger-service` service returned elevated payment
failures for 47 minutes. Approximately 33,792 customer payment
attempts failed during the window. Severity was classified as SEV2.

## Impact

- Failed payment authorisations: 33,792
- Customer-facing duration: 47 minutes
- Affected regions: all regions

## Timeline

- T+0: Error rate on `ledger-service` crossed the 2% alert threshold.
- T+4m: On-call engineer paged and incident channel opened.
- T+19m: Root cause identified.
- T+47m: Service restored and error rate returned to baseline.

## Root Cause

**Schema migration lock.** An online migration held an exclusive lock on the transactions table, blocking writes from the authorisation path.

## Remediation

Use non-blocking migrations and run them outside the peak window.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `ledger-service`.
- Track the fix in the payments reliability backlog.

