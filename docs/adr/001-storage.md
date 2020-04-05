# ADR 001: SQLite WAL with a single domain writer

Status: accepted for the local diagnostic profile.

A PostgreSQL deployment would support multi-host writers, but adds a service and migration surface to the bounded local profile. SQLite supplies transactions, foreign keys and WAL without another process.

Decision: All factual writes and publications share BEGIN IMMEDIATE. Update/delete triggers protect journal, derived history and audit tables. The Go worker serializes access to one connection.

Consequence: This is not a distributed write design. Large provider loads and multi-host failover require a separate migration and concurrent writer campaign. The public contract explicitly names SQLite as the implemented equivalent storage.
