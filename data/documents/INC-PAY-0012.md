---
doc_id: "INC-PAY-0012"
title: "Incident Report: payment failures on ledger-service (2026-04-11)"
department: "payments"
document_type: "incident"
access_level: "internal"
created_date: "2026-04-11"
tags: ["payment", "outage", "incident", "retry-storm-after-partial-failure"]
---

# Incident Report: payment failures on ledger-service (2026-04-11)

## Summary

On 2026-04-11 the `ledger-service` service returned elevated payment
failures for 47 minutes. Approximately 16,562 customer payment
attempts failed during the window. Severity was classified as SEV1.

## Impact

- Failed payment authorisations: 16,562
- Customer-facing duration: 47 minutes
- Affected regions: AP-South

## Timeline

- T+0: Error rate on `ledger-service` crossed the 2% alert threshold.
- T+14m: On-call engineer paged and incident channel opened.
- T+53m: Root cause identified.
- T+47m: Service restored and error rate returned to baseline.

## Root Cause

**Retry storm after partial failure.** Clients retried failed authorisations without backoff, multiplying load on an already degraded service and delaying recovery.

## Remediation

Enforce exponential backoff with jitter and an idempotency key.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `ledger-service`.
- Track the fix in the payments reliability backlog.

