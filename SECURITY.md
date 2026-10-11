# Security Considerations

## Authorized Data

Use synthetic or authorized alerts and inventories.
Evidence references are descriptive strings, not executable instructions.

No outbound messaging, scanning, ticket creation or remediation occurs.

## Trusted Inputs

Source identifiers, operator labels, timestamps and asset metadata are
supplied laboratory inputs. They are not proof of authenticity.

A stable namespace is essential for idempotence.
Fingerprints identify normalized content, not its origin.

## Persistent Data

Protect SQLite files and their parent directories.
Audit history can be modified by someone with database access.
The application does not provide tamper-proof logging.

Each alert and each transition has its own transaction.
Batch processing and stdout publication do not share one transaction.
A later failure does not undo earlier committed changes.

## Reports

Reports can contain sensitive alert metadata.
Keep private inputs, databases and generated reports outside public Git.

Shell redirection is managed by the caller and may replace existing files.
Use new report paths in directories you control.

## Workflow

Operator labels are not an authorization system.
Expected-state checks detect stale commands but do not authenticate callers.

Priority is an explainable laboratory rule, not proof of incident severity.

## Reporting Issues

Provide minimized synthetic reproductions without private evidence,
credentials or confidential asset details.
