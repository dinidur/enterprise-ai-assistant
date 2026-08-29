---
doc_id: "INC-GEN-0006"
title: "Incident Report: notification-dispatcher degradation (2025-11-14)"
department: "platform"
document_type: "incident"
access_level: "public"
created_date: "2025-11-14"
tags: ["incident", "platform"]
---

# Incident Report: notification-dispatcher degradation (2025-11-14)

## Summary

A degradation in `notification-dispatcher` affected the platform domain on
2025-11-14.

## Root Cause

A cache stampede followed an unplanned cache flush.

## Remediation

Introduced request coalescing in front of the cache.

