---
doc_id: "INC-GEN-0005"
title: "Incident Report: payment-authorisation-api degradation (2026-04-20)"
department: "customer-support"
document_type: "incident"
access_level: "internal"
created_date: "2026-04-20"
tags: ["incident", "customer-support"]
---

# Incident Report: payment-authorisation-api degradation (2026-04-20)

## Summary

A degradation in `payment-authorisation-api` affected the customer-support domain on
2026-04-20.

## Root Cause

A cache stampede followed an unplanned cache flush.

## Remediation

Reverted the change and added a canary stage to the deployment pipeline.

