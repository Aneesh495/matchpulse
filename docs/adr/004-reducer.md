# ADR 004: Recompute the affected fixture before optimizing

Status: accepted for the local diagnostic profile.

Incremental caches would reduce cost but make correction propagation and role exposure harder to audit initially. Rebuilding the whole database would be wasteful.

Decision: Select current event revisions and retractions, then reduce only the affected fixture. Bound the journal at 50,000 deliveries. Save immutable snapshots and emit invalidation.

Consequence: This leaves an explicit incremental-processing requirement incomplete. Benchmarks must include retractions and long histories before a checkpoint cache can replace the reference path.
