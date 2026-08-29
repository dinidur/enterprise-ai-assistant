---
doc_id: "INC-GEN-0003"
title: "Incident Report: notification-dispatcher degradation (2026-06-01)"
department: "customer-support"
document_type: "incident"
access_level: "public"
created_date: "2026-06-01"
tags: ["incident", "customer-support"]
---

# Incident Report: notification-dispatcher degradation (2026-06-01)

## Summary

A degradation in `notification-dispatcher` affected the customer-support domain on
2026-06-01.

## Root Cause

A dependency upgrade introduced an incompatible serialisation format.

## Remediation

Added a disk-usage alert at 75% and automated log rotation.

