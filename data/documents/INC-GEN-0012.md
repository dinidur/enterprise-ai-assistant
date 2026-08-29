---
doc_id: "INC-GEN-0012"
title: "Incident Report: fraud-scoring-api degradation (2025-09-24)"
department: "platform"
document_type: "incident"
access_level: "internal"
created_date: "2025-09-24"
tags: ["incident", "platform"]
---

# Incident Report: fraud-scoring-api degradation (2025-09-24)

## Summary

A degradation in `fraud-scoring-api` affected the platform domain on
2025-09-24.

## Root Cause

A misconfigured autoscaling policy removed capacity during peak load.

## Remediation

Reverted the change and added a canary stage to the deployment pipeline.

