---
doc_id: "INC-PAY-0008"
title: "Incident Report: payment failures on ledger-service (2026-02-19)"
department: "payments"
document_type: "incident"
access_level: "internal"
created_date: "2026-02-19"
tags: ["payment", "outage", "incident", "expired-tls-certificate"]
---

# Incident Report: payment failures on ledger-service (2026-02-19)

## Summary

On 2026-02-19 the `ledger-service` service returned elevated payment
failures for 53 minutes. Approximately 24,660 customer payment
attempts failed during the window. Severity was classified as SEV3.

## Impact

- Failed payment authorisations: 24,660
- Customer-facing duration: 53 minutes
- Affected regions: AP-South

## Timeline

- T+0: Error rate on `ledger-service` crossed the 2% alert threshold.
- T+6m: On-call engineer paged and incident channel opened.
- T+58m: Root cause identified.
- T+53m: Service restored and error rate returned to baseline.

## Root Cause

**Expired TLS certificate.** The mutual-TLS certificate used with the settlement partner expired and was not rotated, rejecting every settlement handshake.

## Remediation

Automate certificate rotation and alert 30 days before expiry.

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `ledger-service`.
- Track the fix in the payments reliability backlog.

