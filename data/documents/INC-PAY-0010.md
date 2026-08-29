---
doc_id: "INC-PAY-0010"
title: "Incident Report: payment failures on settlement-worker (2026-03-11)"
department: "payments"
document_type: "incident"
access_level: "internal"
created_date: "2026-03-11"
tags: ["payment", "outage", "incident", "schema-migration-lock"]
---

# Incident Report: payment failures on settlement-worker (2026-03-11)

## Summary

On 2026-03-11 the `settlement-worker` service returned elevated payment
failures for 227 minutes. Approximately 4,065 customer payment
attempts failed during the window. Severity was classified as SEV3.

## Impact

- Failed payment authorisations: 4,065
- Customer-facing duration: 227 minutes
- Affected regions: US-East

## Timeline

- T+0: Error rate on `settlement-worker` crossed the 2% alert threshold.
- T+3m: On-call engineer paged and incident channel opened.
- T+36m: Root cause identified.
- T+227m: Service restored and error rate returned to baseline.

## Root Cause

**Schema migration lock.** An online migration held an exclusive lock on the transactions table, blocking writes from the authorisation path.

## Remediation

Use non-blocking migrations and run them outside the peak window.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `settlement-worker`.
- Track the fix in the payments reliability backlog.

