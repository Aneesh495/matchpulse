# ADR 007: Use a durable outbox and resumable SSE

Status: accepted for the local diagnostic profile.

An in-memory broadcast is simple but loses publications on restart and can race initial snapshots. WebSocket state adds unnecessary protocol machinery for one-way updates.

Decision: Store every stream record in the same transaction as the snapshot and estimates. SSE resumes by monotonic ID, with a sequence-tagged recovery snapshot for new clients.

Consequence: Polling the local outbox costs work per client. The 128-client bound and write deadlines protect memory, but production fan-out needs independent load evidence.
