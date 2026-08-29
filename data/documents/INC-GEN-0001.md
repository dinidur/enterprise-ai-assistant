---
doc_id: "INC-GEN-0001"
title: "Incident Report: settlement-worker degradation (2025-06-01)"
department: "platform"
document_type: "incident"
access_level: "confidential"
created_date: "2025-06-01"
tags: ["incident", "platform"]
---

# Incident Report: settlement-worker degradation (2025-06-01)

## Summary

A degradation in `settlement-worker` affected the platform domain on
2025-06-01.

## Root Cause

A misconfigured autoscaling policy removed capacity during peak load.

## Remediation

Reverted the change and added a canary stage to the deployment pipeline.

