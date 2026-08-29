---
doc_id: "INC-GEN-0009"
title: "Incident Report: settlement-worker degradation (2025-11-21)"
department: "customer-support"
document_type: "incident"
access_level: "public"
created_date: "2025-11-21"
tags: ["incident", "customer-support"]
---

# Incident Report: settlement-worker degradation (2025-11-21)

## Summary

A degradation in `settlement-worker` affected the customer-support domain on
2025-11-21.

## Root Cause

A cache stampede followed an unplanned cache flush.

## Remediation

Added a disk-usage alert at 75% and automated log rotation.

