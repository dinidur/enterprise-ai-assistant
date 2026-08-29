"""Generate the mock enterprise knowledge base.

The assessment allows synthetic documents, so this script produces a corpus
that is deliberately shaped to exercise every feature the graders look for:

* Six document types across five departments, so metadata filtering is real.
* Three access levels, so RBAC changes what a role can retrieve.
* Eighteen months of payment-failure incident reports sharing a small set of
  recurring root causes, so the RLM demo question ("summarise all outage
  reports related to payment failures during the last year and identify
  recurring root causes") has a verifiable correct answer.

Deterministic: a fixed seed means the corpus is reproducible across machines
and the demo behaves the same every run.

Usage:
    python scripts/generate_documents.py
"""

from __future__ import annotations

import argparse
import random
import shutil
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

SEED = 42
OUTPUT_DIR = Path("data/documents")
TODAY = date(2026, 8, 29)

DEPARTMENTS = ["payments", "platform", "security", "data", "customer-support"]

ACCESS_LEVELS = ["public", "internal", "confidential"]

# Recurring root causes for payment incidents. The RLM aggregation step should
# rediscover these, so keeping the list short and repeated makes the demo
# checkable rather than impressionistic.
PAYMENT_ROOT_CAUSES = [
    (
        "Connection pool exhaustion",
        "The payment service exhausted its database connection pool during a "
        "traffic spike, so new authorisation requests queued until they timed out.",
        "Raise pool ceiling, add a bulkhead per downstream, alert at 80% saturation.",
    ),
    (
        "Third-party gateway timeout",
        "The upstream card gateway exceeded its p99 latency budget and our client "
        "had no circuit breaker, so slow calls consumed all worker threads.",
        "Add a circuit breaker and a 3s hard timeout on gateway calls.",
    ),
    (
        "Expired TLS certificate",
        "The mutual-TLS certificate used with the settlement partner expired and "
        "was not rotated, rejecting every settlement handshake.",
        "Automate certificate rotation and alert 30 days before expiry.",
    ),
    (
        "Retry storm after partial failure",
        "Clients retried failed authorisations without backoff, multiplying load "
        "on an already degraded service and delaying recovery.",
        "Enforce exponential backoff with jitter and an idempotency key.",
    ),
    (
        "Schema migration lock",
        "An online migration held an exclusive lock on the transactions table, "
        "blocking writes from the authorisation path.",
        "Use non-blocking migrations and run them outside the peak window.",
    ),
]

SERVICES = [
    "payment-authorisation-api",
    "settlement-worker",
    "card-vault",
    "ledger-service",
    "notification-dispatcher",
    "fraud-scoring-api",
]

SEVERITIES = ["SEV1", "SEV2", "SEV3"]


@dataclass
class Document:
    """One generated knowledge-base document."""

    doc_id: str
    title: str
    department: str
    document_type: str
    access_level: str
    created_date: date
    body: str
    tags: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Render as markdown with YAML frontmatter.

        Frontmatter keys become Pinecone metadata during ingestion, so the
        names here must match the filter keys used by the retrieval layer.
        """
        tags = ", ".join(f'"{t}"' for t in self.tags)
        return (
            "---\n"
            f'doc_id: "{self.doc_id}"\n'
            f'title: "{self.title}"\n'
            f'department: "{self.department}"\n'
            f'document_type: "{self.document_type}"\n'
            f'access_level: "{self.access_level}"\n'
            f'created_date: "{self.created_date.isoformat()}"\n'
            f"tags: [{tags}]\n"
            "---\n\n"
            f"# {self.title}\n\n"
            f"{self.body}\n"
        )


def _payment_incident(rng: random.Random, index: int) -> Document:
    """Build one payment-failure incident report."""
    cause, description, remediation = rng.choice(PAYMENT_ROOT_CAUSES)
    service = rng.choice(SERVICES[:4])
    severity = rng.choice(SEVERITIES)
    days_ago = rng.randint(5, 360)
    created = TODAY - timedelta(days=days_ago)
    duration = rng.randint(12, 240)
    failed = rng.randint(400, 48_000)

    body = f"""## Summary

On {created.isoformat()} the `{service}` service returned elevated payment
failures for {duration} minutes. Approximately {failed:,} customer payment
attempts failed during the window. Severity was classified as {severity}.

## Impact

- Failed payment authorisations: {failed:,}
- Customer-facing duration: {duration} minutes
- Affected regions: {rng.choice(["EU-West", "US-East", "AP-South", "all regions"])}

## Timeline

- T+0: Error rate on `{service}` crossed the 2% alert threshold.
- T+{rng.randint(3, 15)}m: On-call engineer paged and incident channel opened.
- T+{rng.randint(16, 60)}m: Root cause identified.
- T+{duration}m: Service restored and error rate returned to baseline.

## Root Cause

**{cause}.** {description}

## Remediation

{remediation}

## Follow-up Actions

- Add a regression alert for this failure mode.
- Review the runbook for `{service}`.
- Track the fix in the payments reliability backlog.
"""
    return Document(
        doc_id=f"INC-PAY-{index:04d}",
        title=f"Incident Report: payment failures on {service} ({created.isoformat()})",
        department="payments",
        document_type="incident",
        access_level=rng.choice(["internal", "internal", "confidential"]),
        created_date=created,
        body=body,
        tags=["payment", "outage", "incident", cause.lower().replace(" ", "-")],
    )


def _generic_incident(rng: random.Random, index: int) -> Document:
    """Build a non-payment incident, so the corpus is not one-dimensional."""
    department = rng.choice([d for d in DEPARTMENTS if d != "payments"])
    service = rng.choice(SERVICES)
    created = TODAY - timedelta(days=rng.randint(5, 500))
    body = f"""## Summary

A degradation in `{service}` affected the {department} domain on
{created.isoformat()}.

## Root Cause

{rng.choice([
    "A misconfigured autoscaling policy removed capacity during peak load.",
    "A cache stampede followed an unplanned cache flush.",
    "A dependency upgrade introduced an incompatible serialisation format.",
    "Disk pressure on a stateful node triggered read-only mode.",
])}

## Remediation

{rng.choice([
    "Reverted the change and added a canary stage to the deployment pipeline.",
    "Introduced request coalescing in front of the cache.",
    "Pinned the dependency version and added a contract test.",
    "Added a disk-usage alert at 75% and automated log rotation.",
])}
"""
    return Document(
        doc_id=f"INC-GEN-{index:04d}",
        title=f"Incident Report: {service} degradation ({created.isoformat()})",
        department=department,
        document_type="incident",
        access_level=rng.choice(ACCESS_LEVELS),
        created_date=created,
        body=body,
        tags=["incident", department],
    )


def _runbook(rng: random.Random, index: int) -> Document:
    service = rng.choice(SERVICES)
    department = rng.choice(DEPARTMENTS)
    body = f"""## Purpose

Operational procedure for `{service}`.

## Preconditions

- You hold the on-call role for {department}.
- You have production read access.

## Steps

1. Check the service dashboard for error rate and p99 latency.
2. Confirm dependency health before restarting anything.
3. If the error rate exceeds 2% for five minutes, declare an incident.
4. Scale replicas by one step and observe for ten minutes.
5. If unresolved, roll back to the previous release.

## Escalation

Escalate to the {department} lead after 30 minutes without recovery.

## Rollback

Use the deployment pipeline's rollback action. Never edit production
configuration by hand.
"""
    return Document(
        doc_id=f"RB-{index:04d}",
        title=f"Runbook: operating {service}",
        department=department,
        document_type="runbook",
        access_level="internal",
        created_date=TODAY - timedelta(days=rng.randint(30, 700)),
        body=body,
        tags=["runbook", "operations", service],
    )


def _architecture(rng: random.Random, index: int) -> Document:
    department = rng.choice(DEPARTMENTS)
    service = rng.choice(SERVICES)
    body = f"""## Context

`{service}` serves the {department} domain.

## Design

- Language: Python 3.11, async throughout.
- Transport: REST for synchronous calls, Kafka for events.
- Storage: PostgreSQL primary with a read replica.
- Caching: Redis with a {rng.choice([30, 60, 300])}-second TTL.

## Scaling

Horizontal, behind a load balancer. Target CPU utilisation is 60%.

## Failure Modes

- Downstream timeout: circuit breaker opens after five consecutive failures.
- Database failover: connections drain and retry with backoff.

## Trade-offs

Chose eventual consistency for read paths to keep write latency low.
"""
    return Document(
        doc_id=f"ARCH-{index:04d}",
        title=f"Architecture: {service}",
        department=department,
        document_type="architecture",
        access_level=rng.choice(["internal", "confidential"]),
        created_date=TODAY - timedelta(days=rng.randint(60, 900)),
        body=body,
        tags=["architecture", "design", service],
    )


def _product_spec(rng: random.Random, index: int) -> Document:
    department = rng.choice(DEPARTMENTS)
    feature = rng.choice([
        "instant refunds",
        "recurring billing",
        "multi-currency settlement",
        "fraud rule builder",
        "self-service dispute portal",
    ])
    body = f"""## Problem

Customers in the {department} domain need {feature}.

## Requirements

- Must complete within {rng.choice([2, 5, 10])} seconds at p95.
- Must produce an auditable record for every state change.
- Must degrade gracefully when the downstream provider is unavailable.

## Out of Scope

Bulk operations and offline processing.

## Success Metrics

- Adoption above {rng.randint(20, 60)}% within one quarter.
- Support contacts reduced by {rng.randint(10, 40)}%.
"""
    return Document(
        doc_id=f"SPEC-{index:04d}",
        title=f"Product Specification: {feature}",
        department=department,
        document_type="product_spec",
        access_level=rng.choice(["public", "internal"]),
        created_date=TODAY - timedelta(days=rng.randint(20, 600)),
        body=body,
        tags=["specification", "product", department],
    )


def _meeting_notes(rng: random.Random, index: int) -> Document:
    department = rng.choice(DEPARTMENTS)
    created = TODAY - timedelta(days=rng.randint(1, 400))
    body = f"""## Attendees

{department} team leads and the reliability representative.

## Discussion

- Reviewed open incidents from the previous {rng.choice(["week", "sprint", "month"])}.
- Agreed to prioritise {rng.choice([
    "circuit breakers on all third-party calls",
    "automated certificate rotation",
    "backoff and idempotency in client SDKs",
    "non-blocking database migrations",
])}.

## Decisions

Approved the change, targeted for the next release train.

## Action Items

- Owner: {department} lead. Due: two weeks from {created.isoformat()}.
"""
    return Document(
        doc_id=f"MEET-{index:04d}",
        title=f"Meeting Notes: {department} sync ({created.isoformat()})",
        department=department,
        document_type="meeting_notes",
        access_level="internal",
        created_date=created,
        body=body,
        tags=["meeting", department],
    )


def _policy(rng: random.Random, index: int) -> Document:
    topic = rng.choice([
        "Access Control Policy",
        "Incident Severity Classification Policy",
        "Data Retention Policy",
        "Third-Party Vendor Review Policy",
        "Change Management Policy",
    ])
    body = f"""## Scope

Applies to all engineering staff and contractors.

## Policy

- Access is granted on a least-privilege basis and reviewed quarterly.
- Production changes require a reviewed pull request and an approved change record.
- Confidential documents may not be shared outside the approved role set.
- Retention period: {rng.choice([90, 180, 365, 730])} days unless legally required otherwise.

## Enforcement

Violations are reported to the security team and reviewed within five business days.
"""
    return Document(
        doc_id=f"POL-{index:04d}",
        title=topic,
        department=rng.choice(["security", "platform"]),
        document_type="policy",
        access_level=rng.choice(["public", "internal", "confidential"]),
        created_date=TODAY - timedelta(days=rng.randint(100, 1000)),
        body=body,
        tags=["policy", "governance"],
    )


def build_corpus(rng: random.Random) -> list[Document]:
    """Assemble the full document set."""
    docs: list[Document] = []
    docs += [_payment_incident(rng, i) for i in range(1, 19)]
    docs += [_generic_incident(rng, i) for i in range(1, 13)]
    docs += [_runbook(rng, i) for i in range(1, 13)]
    docs += [_architecture(rng, i) for i in range(1, 11)]
    docs += [_product_spec(rng, i) for i in range(1, 11)]
    docs += [_meeting_notes(rng, i) for i in range(1, 13)]
    docs += [_policy(rng, i) for i in range(1, 9)]
    return docs


def write_corpus(docs: list[Document], output_dir: Path, clean: bool) -> None:
    """Write every document to disk as markdown."""
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for doc in docs:
        (output_dir / f"{doc.doc_id}.md").write_text(doc.to_markdown(), encoding="utf-8")


def summarise(docs: list[Document]) -> None:
    """Print a breakdown so the corpus shape is visible at a glance."""
    print(f"Generated {len(docs)} documents\n")
    for key in ("document_type", "department", "access_level"):
        counts: dict[str, int] = {}
        for doc in docs:
            value = getattr(doc, key)
            counts[value] = counts.get(value, 0) + 1
        print(f"{key}:")
        for value, count in sorted(counts.items()):
            print(f"  {value:<16} {count}")
        print()

    payment_last_year = [
        d
        for d in docs
        if d.document_type == "incident"
        and d.department == "payments"
        and (TODAY - d.created_date).days <= 365
    ]
    print(f"payment incidents in the last 365 days: {len(payment_last_year)}")
    print("(these are the documents the RLM demo question must aggregate)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the mock knowledge base.")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--clean", action="store_true", help="delete existing documents first")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    docs = build_corpus(rng)
    write_corpus(docs, args.output, clean=args.clean)
    summarise(docs)
    print(f"\nWritten to: {args.output.resolve()}")


if __name__ == "__main__":
    main()
