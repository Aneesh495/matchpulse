# Recovery runbook

Stop the Go service with SIGINT. It drains requests for up to five seconds, then closes the owned Python worker. SQLite WAL and FULL synchronous commits own durability. Keep the database together with its WAL and shared-memory companions when copying an active service; prefer a stopped service or SQLite backup API. A partial filesystem copy of a live database is not a verified backup.

An injected exception after journal append or before commit rolls back journal, snapshots, estimates and outbox. The deterministic integration suite exercises both positions. If a child worker exits or a request times out, Go kills it, waits for exit and starts a new child for the next admitted request. A client retry uses the same event/revision key. An already committed duplicate produces no new stream publication. A conflicting duplicate fails for review.

After browser disconnect, EventSource reconnects with Last-Event-ID. The service reads durable records after that ID. A brand new client receives a recovery snapshot and its sequence. A future cursor is also recovered. Slow writes terminate after five seconds. SSE is at-least-once delivery; apply only increasing IDs. The service does not impose upstream provider freshness on the archive clock.

If storage guard fails, stop acquisitions and reserve no new checkpoints. Inspect `make doctor`. Preserve unique evidence and source before deleting project-owned disposable caches. The storage guard conservatively reserves the entire shared npm and Go build caches because exact attribution is not assumed. This implementation has no external Go module downloads. Acquired data, generated outputs, clean checkouts and model states live under the project budget.

Interrupted diagnostic training preserves each completed model atomically. A completed run directory cannot be overwritten. Optimizer state is restorable; an end-to-end epoch-resume command is not yet implemented. A stale `.tmp` file is deliberately not overwritten without inspection. Keep the original and start a new ID after documenting interruption. Full campaign continuation remains blocked until lawful input identities and budgets are frozen.
