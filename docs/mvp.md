# MVP Scope and Threat Model

## Goal

Build an offline SOC triage orchestrator with persistent, auditable processing.
Convert authorized synthetic alerts into deterministic investigation cases.

No live response, external ticket creation or message delivery is performed.

## Inputs

Validated JSONL alerts contain:

- Source namespace and source alert identifier.
- UTC occurrence timestamp.
- Alert category and severity.
- Host identifier and optional source IP.
- Bounded evidence references.

Source metadata is supplied evidence, not proof of authenticity.
Do not ingest arbitrary executable playbook definitions.

## Processing

1. Validate bounded input and strict configuration.
2. Identify each alert using its source namespace and identifier.
3. Calculate a fingerprint over normalized alert content.
4. Persist an alert and investigation case transactionally.
5. Apply a reviewed deterministic triage policy.
6. Record state transitions in an append-only application audit history.
7. Export explainable investigation reports.

## Idempotence

Repeating an identical normalized alert must not create another case.

Reusing the same source identity with different normalized content must
produce an explicit conflict, not silently overwrite existing evidence.

An input namespace must remain stable across repeated imports.

## Workflow

Initial states:

- new
- investigating
- closed

Allowed transitions are explicit.
Changing state requires a reason and an operator label.
These labels are audit metadata, not authenticated production identities.

Alert severity and case priority are separate concepts.
Policy decisions must include their effective settings and rationale.

## Persistence and Recovery

Use SQLite transactions for alert, case and audit creation.
Database failures must not be reported as successful processing.

Repeated imports after restart must retain idempotent behavior.
Reports and database changes are not assumed to share one transaction.

## Enrichment

The MVP uses an explicitly labeled local synthetic asset inventory.
It records lookup outcomes and missing inventory entries.

No external reputation API is required.
A missing inventory entry must not imply that an asset is safe.

## Validation

Test:

- Valid alert creating one case.
- Repeated identical alert producing no duplicate case.
- Same identity with changed content producing a conflict.
- Persistence across restart.
- Allowed and forbidden workflow transitions.
- Audit entries retained after transitions.
- Unknown assets and invalid input.
- Storage and export failures.

Evaluate decision correctness against independently defined fixtures.
Measure reliability and performance only from actual recorded executions.

## Security Boundaries

No automatic blocking, scanning, shell execution or remediation.
No email, Slack or external ticketing calls.
No claim that rule-based triage determines whether an incident is real.

The local CLI is a laboratory harness, not a production authorization system.
SQLite audit history is not tamper-proof against a database administrator.

## Future Extensions

- Explicit adapter for SOC Evidence Pipeline reports.
- Reviewed outbound integrations using an outbox and idempotency keys.
- Retry and dead-letter handling for those integrations.
- Authenticated operators and stronger audit-integrity controls.
