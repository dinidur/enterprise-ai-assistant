---
doc_id: "INC-PAY-0004"
title: "Incident Report: payment failures on payment-authorisation-api (2026-01-20)"
department: "payments"
document_type: "incident"
access_level: "internal"
created_date: "2026-01-20"
tags: ["payment", "outage", "incident", "expired-tls-certificate"]
---

# Incident Report: payment failures on payment-authorisation-api (2026-01-20)

## Summary

On 2026-01-20 the `payment-authorisation-api` service returned elevated payment
failures for 99 minutes. Approximately 18,610 customer payment
attempts failed during the window. Severity was classified as SEV1.

## Impact

- Failed payment authorisations: 18,610
- Customer-facing duration: 99 minutes
- Affected regions: US-East

## Timeline

- T+0: Error rate on `payment-authorisation-api` crossed the 2% alert threshold.
- T+6m: On-call engineer paged and incident channel opened.
- T+37m: Root cause identified.
- T+99m: Service restored and error rate returned to baseline.

## Root Cause

**Expired TLS certificate.** The mutual-TLS certificate used with the settlement partner expired and was not rotated, rejecting every settlement handshake.

## Remediation

Automate certificate rotation and alert 30 days before expiry.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `payment-authorisation-api`.
- Track the fix in the payments reliability backlog.

