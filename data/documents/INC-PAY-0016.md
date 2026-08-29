---
doc_id: "INC-PAY-0016"
title: "Incident Report: payment failures on payment-authorisation-api (2026-01-14)"
department: "payments"
document_type: "incident"
access_level: "confidential"
created_date: "2026-01-14"
tags: ["payment", "outage", "incident", "expired-tls-certificate"]
---

# Incident Report: payment failures on payment-authorisation-api (2026-01-14)

## Summary

On 2026-01-14 the `payment-authorisation-api` service returned elevated payment
failures for 52 minutes. Approximately 30,135 customer payment
attempts failed during the window. Severity was classified as SEV2.

## Impact

- Failed payment authorisations: 30,135
- Customer-facing duration: 52 minutes
- Affected regions: EU-West

## Timeline

- T+0: Error rate on `payment-authorisation-api` crossed the 2% alert threshold.
- T+14m: On-call engineer paged and incident channel opened.
- T+32m: Root cause identified.
- T+52m: Service restored and error rate returned to baseline.

## Root Cause

**Expired TLS certificate.** The mutual-TLS certificate used with the settlement partner expired and was not rotated, rejecting every settlement handshake.

## Remediation

Automate certificate rotation and alert 30 days before expiry.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `payment-authorisation-api`.
- Track the fix in the payments reliability backlog.

