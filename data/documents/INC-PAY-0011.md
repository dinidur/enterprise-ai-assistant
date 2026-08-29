---
doc_id: "INC-PAY-0011"
title: "Incident Report: payment failures on payment-authorisation-api (2025-11-07)"
department: "payments"
document_type: "incident"
access_level: "internal"
created_date: "2025-11-07"
tags: ["payment", "outage", "incident", "expired-tls-certificate"]
---

# Incident Report: payment failures on payment-authorisation-api (2025-11-07)

## Summary

On 2025-11-07 the `payment-authorisation-api` service returned elevated payment
failures for 236 minutes. Approximately 47,449 customer payment
attempts failed during the window. Severity was classified as SEV1.

## Impact

- Failed payment authorisations: 47,449
- Customer-facing duration: 236 minutes
- Affected regions: AP-South

## Timeline

- T+0: Error rate on `payment-authorisation-api` crossed the 2% alert threshold.
- T+6m: On-call engineer paged and incident channel opened.
- T+57m: Root cause identified.
- T+236m: Service restored and error rate returned to baseline.

## Root Cause

**Expired TLS certificate.** The mutual-TLS certificate used with the settlement partner expired and was not rotated, rejecting every settlement handshake.

## Remediation

Automate certificate rotation and alert 30 days before expiry.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `payment-authorisation-api`.
- Track the fix in the payments reliability backlog.

