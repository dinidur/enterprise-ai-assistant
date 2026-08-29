---
doc_id: "INC-GEN-0002"
title: "Incident Report: payment-authorisation-api degradation (2025-07-31)"
department: "customer-support"
document_type: "incident"
access_level: "confidential"
created_date: "2025-07-31"
tags: ["incident", "customer-support"]
---

# Incident Report: payment-authorisation-api degradation (2025-07-31)

## Summary

A degradation in `payment-authorisation-api` affected the customer-support domain on
2025-07-31.

## Root Cause

A cache stampede followed an unplanned cache flush.

## Remediation

Introduced request coalescing in front of the cache.

