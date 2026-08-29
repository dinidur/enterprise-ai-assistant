---
doc_id: "INC-PAY-0017"
title: "Incident Report: payment failures on payment-authorisation-api (2026-03-25)"
department: "payments"
document_type: "incident"
access_level: "internal"
created_date: "2026-03-25"
tags: ["payment", "outage", "incident", "third-party-gateway-timeout"]
---

# Incident Report: payment failures on payment-authorisation-api (2026-03-25)

## Summary

On 2026-03-25 the `payment-authorisation-api` service returned elevated payment
failures for 227 minutes. Approximately 42,274 customer payment
attempts failed during the window. Severity was classified as SEV3.

## Impact

- Failed payment authorisations: 42,274
- Customer-facing duration: 227 minutes
- Affected regions: US-East

## Timeline

- T+0: Error rate on `payment-authorisation-api` crossed the 2% alert threshold.
- T+5m: On-call engineer paged and incident channel opened.
- T+39m: Root cause identified.
- T+227m: Service restored and error rate returned to baseline.

## Root Cause

**Third-party gateway timeout.** The upstream card gateway exceeded its p99 latency budget and our client had no circuit breaker, so slow calls consumed all worker threads.

## Remediation

Add a circuit breaker and a 3s hard timeout on gateway calls.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `payment-authorisation-api`.
- Track the fix in the payments reliability backlog.

