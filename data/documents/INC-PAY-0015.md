---
doc_id: "INC-PAY-0015"
title: "Incident Report: payment failures on card-vault (2026-08-19)"
department: "payments"
document_type: "incident"
access_level: "internal"
created_date: "2026-08-19"
tags: ["payment", "outage", "incident", "schema-migration-lock"]
---

# Incident Report: payment failures on card-vault (2026-08-19)

## Summary

On 2026-08-19 the `card-vault` service returned elevated payment
failures for 186 minutes. Approximately 47,633 customer payment
attempts failed during the window. Severity was classified as SEV3.

## Impact

- Failed payment authorisations: 47,633
- Customer-facing duration: 186 minutes
- Affected regions: EU-West

## Timeline

- T+0: Error rate on `card-vault` crossed the 2% alert threshold.
- T+13m: On-call engineer paged and incident channel opened.
- T+50m: Root cause identified.
- T+186m: Service restored and error rate returned to baseline.

## Root Cause

**Schema migration lock.** An online migration held an exclusive lock on the transactions table, blocking writes from the authorisation path.

## Remediation

Use non-blocking migrations and run them outside the peak window.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `card-vault`.
- Track the fix in the payments reliability backlog.

