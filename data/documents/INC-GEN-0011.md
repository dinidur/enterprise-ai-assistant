---
doc_id: "INC-GEN-0011"
title: "Incident Report: card-vault degradation (2026-01-20)"
department: "customer-support"
document_type: "incident"
access_level: "confidential"
created_date: "2026-01-20"
tags: ["incident", "customer-support"]
---

# Incident Report: card-vault degradation (2026-01-20)

## Summary

A degradation in `card-vault` affected the customer-support domain on
2026-01-20.

## Root Cause

Disk pressure on a stateful node triggered read-only mode.

## Remediation

Added a disk-usage alert at 75% and automated log rotation.

