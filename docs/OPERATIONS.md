# Local operator paths

These operations need no external account or paid resources. The shipped context example is fictional. A real source needs its own rights, acquisition identity and canonical person map.

## Import source context

Stop the service before direct database imports. The packet importer commits source declarations, people and context as one transaction. A malformed fact rolls back the whole packet. Identical revisions are idempotent; conflicting bytes under the same revision fail.

```sh
make import INPUT=fixtures/context-import.json
make live-demo
```

The example adds coarse availability for the unused fictional substitute Emil Strand. In Match centre inspect him after replay: he has no match rating and has a sourced availability assertion at match valid time. Registration and contract assertions from the authored packet remain separately inspectable. Imported availability never implies an action, diagnosis or causal explanation for nonparticipation.

A packet contains bounded lists named `sources`, `persons`, `fixtures` and `context`. Each context fact has a stable ID, positive revision, canonical person, kind, valid interval, known-at time, source ID, HTTPS evidence URL, confidence, details and optional withdrawal. Supported kinds are contract, registration, role and coarse availability. Unknown fields fail. Contracts require expiry; loans may name a parent club; availability permits available, injured, suspended or unknown and excludes medical detail. Source declarations require an explicit Boolean redistribution field. This is a configuration declaration, not legal proof.

While the service is running, use `POST /api/context` with one fact through the normal Go/Python writer. The body shape is the first context object in the example packet, not the enclosing packet. The source and person must already exist. Each accepted revision publishes a durable context record. No table is overwritten. Open the player again to refresh its context panel.

The current assertion is selected by provider revision among facts known by the cutoff, then filtered by its valid interval. A changed interval or withdrawal cannot resurrect its earlier version. Overlapping contradictory sources remain visible as conflicts rather than silently choosing one. Coverage counts unknown and ambiguous registrations separately.

## Inspect history without future observations

Transfer terminal has an explicit UTC knowledge cutoff. Apply it before comparing up to three people. Their conditional medians, current/prior intervals, move probabilities and separate observed transactions use the same cutoff. Export CSV follows that cutoff. The API equivalents are `/api/ticker?as_of=<UTC>` and `/api/compare?ids=<one-to-three-IDs>&as_of=<UTC>`.

A saved match version automatically supplies its knowledge cutoff to the player drawer. Registry facts additionally use the match's occurrence time. Thus v28 has neither the later post-match estimate nor the later sale, while a corrected latest view may include later knowledge with separate timestamps. The seven-day freshness flag is a declared display policy, not empirical calibration. Archive and fictional estimates remain labeled historical.

CSV includes current/prior bounds, source version, both model IDs, nominal price vintage, horizon, uncertainty reason and freshness clock in addition to its original fields. Unavailable values remain blank. Formula-like strings are escaped; negative numeric deltas remain numeric.

## Resume diagnostic training

```sh
make train RUN_ID=resume-example STOP_AFTER_EPOCHS=1
make train RUN_ID=resume-example RESUME=1
python3 -m matchpulse.verify_training evidence/resume-example
```

The first command intentionally exits nonzero after saving one complete epoch. Resume uses the original input files and restores weights, Adam moments/step, sampler RNG and epoch progress. It rejects changed inputs, changed numerical implementation, incompatible shapes and completed run directories. Completed model artifacts are compared and preserved. An interrupted partial epoch is replayed from the last durable boundary; completed epochs are not trained again.

The regression compares every final model artifact byte-for-byte against an uninterrupted run and checks exactly 42 distinct completed epoch identities. Independent held-out inference verification runs afterward. This establishes recovery mechanics on the synthetic diagnostic, not actual-football model validity.

## Diagnose writer latency

The HTTP load artifact now separates admission queue wait, worker roundtrip, journal append/read, reduction, transaction begin/body and durable commit. Those are actual measured spans. An isolated commit stall can therefore be distinguished from repeated reduction work or waiting behind another request. Full synchronous durability and the original 250 ms gate remain unchanged. Existing failed shared-runner evidence is retained.
