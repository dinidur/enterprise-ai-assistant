---
doc_id: "INC-GEN-0010"
title: "Incident Report: ledger-service degradation (2026-05-19)"
department: "customer-support"
document_type: "incident"
access_level: "confidential"
created_date: "2026-05-19"
tags: ["incident", "customer-support"]
---

# Incident Report: ledger-service degradation (2026-05-19)

## Summary

A degradation in `ledger-service` affected the customer-support domain on
2026-05-19.

## Root Cause

A misconfigured autoscaling policy removed capacity during peak load.

## Remediation

Reverted the change and added a canary stage to the deployment pipeline.

