# Evaluation

## Synthetic Input

The demonstration contains four ordered records:

1. A new HIGH authentication alert.
2. An identical repeated alert.
3. The first identity reused with CRITICAL severity.
4. A separate CRITICAL endpoint alert.

Source identity is namespace plus source alert identifier.
Content fingerprints include normalized severity, timestamp and evidence.

## Observed Results

The first installed-CLI import created two cases, identified one duplicate
and reported one conflict. It returned exit code 1 as specified.

The second import with the same database identified three duplicates
and retained the content conflict. No new case was created.

The first case moved from new to investigating.
Priority remained P2 and its history contained two audit entries.
The supplied operator label and justification were recorded.

## Automated Validation

The latest observed local suite passed 37 tests, covering:

- Input validation and normalized fingerprints.
- Equivalent timezone, IP and evidence-order representation.
- Same identity with changed content preserving original evidence.
- Idempotence across reopening the database.
- Atomic creation rollback when audit insertion fails.
- Allowed and forbidden transitions.
- Stale expected-state rejection.
- State-change rollback on audit insertion failure.
- CLI imports, inspection and transitions.

No concurrent stress or production-scale benchmark has been performed.

## Interpretation

These results establish behavior on predefined synthetic cases.
They do not estimate real-world incident detection accuracy or analyst workload.

Reproducibility concerns decisions and retained state, not identical UUIDs.

## Future Measurements

Measure import throughput, transaction latency, peak memory and contention
using defined alert counts and repeated runs on recorded hardware.

Evaluate process interruptions and subsequent imports.
For policy quality, use independently reviewed priority expectations and
report disagreement without treating source severity as ground truth.
