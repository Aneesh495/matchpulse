# Four execution paths

These paths use the actual executable and domain core. Input is the redistributable authored synthetic packet. No third-party live fixture is implied.

## Action, exposure and player evidence

Run `make live-demo`, then Play replay or Finish. The browser calls the [Go replay endpoint](../internal/server/http.go), which dispatches through the [bounded Python worker](../internal/server/worker.go) to [demo.step](../matchpulse/demo.py). Each authored event goes through [Engine.ingest](../matchpulse/engine.py) and the same contracts as operator-provided envelopes. The pass uses its own supported location/outcome and current score/man context. Active players accrue minutes and a shrunk contribution display. Luca Ferri's saved reason is +0.21 from the authored quality 0.42 save. Inspect his drawer for the exact event ID and model ID. An unused substitute remains unrated.

The deterministic command is `make demo`. It prints every snapshot's score, version and correction count, then final state including conditional estimates and the separate later sale. [Walkthrough tests](../tests/test_demo.py) independently assert keeper contribution, unused-player absence, final score and restart equality.

## VAR, late delivery and historical state

From Match centre select snapshot v28, then v30. The former shows the provisional Harbor goal; the latter shows 0 to 0 and the VAR reason. [Envelope selection](../matchpulse/ratings.py) retains latest provider revisions and retracted targets without deleting facts. The late pass sorts before the original goal by occurrence but enters knowledge only when delivered. Adam Vale's role changes from AM to CM, with visible role history. The later legitimate goal and its quality revision produce v37 full time at 1 to 0.

The [independent verifier](../matchpulse/verify.py) replays goal/retraction logic separately and recomputes the pass probability from only preceding known events. Its future-feature tampering control changes the stored before probability, rehashes the bundle and must fail with `event-then-future feature leakage`. That differs from merely detecting corrupt bytes.

## Completed match, estimate version and later transaction

Finish the replay, then advance once more. Completion publishes 23 eligible synthetic estimates through [diagnostic_estimate](../matchpulse/valuation.py). The unused substitute is absent. The display includes prior/current intervals, model ID, target, mode and zero differences. A later fictional permanent transaction for Leo Marin appears in its own observation layer at EUR 19 million guaranteed, with optional add-ons separate. It does not replace the conditional estimate or imply a trade in that estimate.

Open Transfer terminal, inspect Leo Marin, then Export CSV. The [CSV handler](../internal/server/http.go) emits mode, known-at, source version, model ID, currency and target. The real Go/Python integration test reads all 23 rows and checks the synthetic mode. A metadata-only correction after completion publishes zero changes; an interrupted completion publishes unavailable estimates, covered in [completion tests](../tests/test_demo.py).

## Failure, rollback, restart and reconnect

Run `make test`. [Engine fault tests](../tests/test_engine.py) inject an exception after journal append and immediately before commit. Both leave no partial snapshot or ticker. The [Go integration test](../internal/server/http_test.go) runs the actual Python child, completes replay, kills the worker, requests state again and verifies the later sale survived. The same test reconnects SSE after sequence 40 and receives sequence 41.

Run `make stress RUN_ID=http-new-id` for 16 concurrent loopback callers and eight durable cursor reconnects. The harness pre-seeds synthetic fixtures, ingests all 592 deliveries and records every processing/roundtrip observation. It checks final score/version per fixture and monotonically increasing stream IDs. This measures service mechanics; source freshness remains unmeasured. `make negative-controls` additionally invokes the real verifier against eight changed bundles, retaining actual subprocess exits and semantic rejection reasons.
