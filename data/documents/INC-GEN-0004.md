---
doc_id: "INC-GEN-0004"
title: "Incident Report: fraud-scoring-api degradation (2026-03-18)"
department: "security"
document_type: "incident"
access_level: "internal"
created_date: "2026-03-18"
tags: ["incident", "security"]
---

# Incident Report: fraud-scoring-api degradation (2026-03-18)

## Summary

A degradation in `fraud-scoring-api` affected the security domain on
2026-03-18.

## Root Cause

Disk pressure on a stateful node triggered read-only mode.

## Remediation

Pinned the dependency version and added a contract test.

