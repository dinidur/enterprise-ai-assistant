---
doc_id: "INC-GEN-0007"
title: "Incident Report: fraud-scoring-api degradation (2025-10-05)"
department: "platform"
document_type: "incident"
access_level: "public"
created_date: "2025-10-05"
tags: ["incident", "platform"]
---

# Incident Report: fraud-scoring-api degradation (2025-10-05)

## Summary

A degradation in `fraud-scoring-api` affected the platform domain on
2025-10-05.

## Root Cause

A misconfigured autoscaling policy removed capacity during peak load.

## Remediation

Introduced request coalescing in front of the cache.

