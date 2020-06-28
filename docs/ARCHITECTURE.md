# Architecture

Go owns HTTP, request cancellation, bounded admission, CSV and Server-Sent Events. A child Python process owns numerical state and one SQLite connection. A newline-delimited JSON protocol serializes domain mutations. A lost worker is killed and recreated against the same database. No in-memory checkpoint is authoritative.

[Engine.ingest](../matchpulse/engine.py) begins an immediate transaction, appends an envelope, reduces the affected fixture, writes a new snapshot, emits invalidation when appropriate, publishes eligible estimates and appends durable stream records. Any exception rolls back every derived publication. Duplicate provider event/revision keys return the existing snapshot; conflicting facts under the same key fail. SQLite triggers reject updates and deletes on factual tables.

The reducer reconstructs only the affected fixture, selecting latest provider revisions and retractions before ordering by period, second and provider ordinal. It is bounded at 50,000 deliveries per fixture. This is a correctness-first implementation with linear replay on each delivery, not the required optimized incremental engine. The local load profile measures its current cost. Indexes constrain match journal lookup, but long production histories require incremental checkpoints and retention design.

Receipt time defines the as-known view. Occurrence time defines match order. Provider publication time may be absent. The archive adapter explicitly preserves that absence and cannot recreate historical provider revisions from a current export. A late fact invalidates earlier derived state without erasing earlier saved snapshots.

The live display uses [RatingReducer](../matchpulse/ratings.py), a declared uncalibrated contextual baseline. Original dense and recurrent models train through [training](../matchpulse/training.py) as separate synthetic diagnostics. They are not silently substituted into the terminal. Learned production model promotion remains unavailable pending actual-data calibration. Transfer diagnostics likewise preserve their own model ID and synthetic target. Actual observation records remain a separate table and UI layer.

The browser requests a snapshot with its global sequence, then consumes durable SSE updates. Reconnect uses Last-Event-ID. A new connection or invalid future cursor receives a recovery snapshot. Streams have five-second write deadlines and a 128-client limit. Engine requests have 64 admission slots, one active worker, and ten-second request deadlines. A full queue returns 503. This bounds admission, not provider-side freshness.

| Diagram | Contract | Owning source |
| --- | --- | --- |
| [Context](diagrams/01-context.svg) | Permission boundary and separate data modes | [adapters](../matchpulse/adapters.py) |
| [Components](diagrams/02-components.svg) | HTTP/RPC/storage split | [server](../internal/server/http.go) |
| [Ownership](diagrams/03-ownership.svg) | One writer and worker lifecycle | [worker](../internal/server/worker.go) |
| [Action path](diagrams/04-action-path.svg) | Envelope to useful output | [engine](../matchpulse/engine.py) |
| [Concurrency](diagrams/05-concurrency.svg) | Admission, durable cursors and clients | [server](../internal/server/http.go) |
| [Lifecycle](diagrams/06-lifecycle.svg) | Completion and retraction | [engine](../matchpulse/engine.py) |
| [Persistence](diagrams/07-persistence.svg) | Atomic bitemporal assertions | [storage](../matchpulse/storage.py) |
| [Numerics](diagrams/08-numerics.svg) | Attribution and display units | [ratings](../matchpulse/ratings.py) |
| [Lineage](diagrams/09-lineage.svg) | Trusted source through raw evidence | [verifier](../matchpulse/verify.py) |
| [Recovery](diagrams/10-recovery.svg) | Rollback, restart and reconnect | [worker](../internal/server/worker.go) |
| [Deployment](diagrams/11-deployment.svg) | Local runtime and external binding | [main](../cmd/matchpulse/main.go) |
| [Testing](diagrams/12-testing.svg) | Independent checks and negative controls | [controls](../matchpulse/negative_controls.py) |

Each SVG has an editable Graphviz source with the same basename. These diagrams describe the implemented local profile. None represents an acquired licensed provider, distributed deployment, or full campaign.

The [source-context path](diagrams/13-context.svg) owns valid/known intervals and conflicts. The [epoch-recovery path](diagrams/14-resume.svg) binds frozen bytes, optimizer/RNG state and exact continuation. Both have editable DOT sources.
