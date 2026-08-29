---
doc_id: "INC-PAY-0006"
title: "Incident Report: payment failures on payment-authorisation-api (2026-07-15)"
department: "payments"
document_type: "incident"
access_level: "confidential"
created_date: "2026-07-15"
tags: ["payment", "outage", "incident", "retry-storm-after-partial-failure"]
---

# Incident Report: payment failures on payment-authorisation-api (2026-07-15)

## Summary

On 2026-07-15 the `payment-authorisation-api` service returned elevated payment
failures for 153 minutes. Approximately 19,613 customer payment
attempts failed during the window. Severity was classified as SEV2.

## Impact

- Failed payment authorisations: 19,613
- Customer-facing duration: 153 minutes
- Affected regions: AP-South

## Timeline

- T+0: Error rate on `payment-authorisation-api` crossed the 2% alert threshold.
- T+12m: On-call engineer paged and incident channel opened.
- T+28m: Root cause identified.
- T+153m: Service restored and error rate returned to baseline.

## Root Cause

**Retry storm after partial failure.** Clients retried failed authorisations without backoff, multiplying load on an already degraded service and delaying recovery.

## Remediation

Enforce exponential backoff with jitter and an idempotency key.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `payment-authorisation-api`.
- Track the fix in the payments reliability backlog.

