# Claim to evidence index

| Claim | Implementation | Independent check or raw evidence | Limit |
| --- | --- | --- | --- |
| Immutable event/revision facts | [storage](../matchpulse/storage.py) | [journal tests](../tests/test_storage.py) | Single SQLite writer |
| Duplicate publication is idempotent | [engine](../matchpulse/engine.py) | [fault/duplicate tests](../tests/test_engine.py) | Unique normalized revision key |
| Prior and corrected score both exist | [reducer](../matchpulse/ratings.py) | Frozen probes plus independent score replay | Authored fixture only |
| No match rating for unused substitute | [PlayerState.view](../matchpulse/ratings.py) | [exposure tests](../tests/test_ratings.py) | Event-only baseline |
| Completion can retract estimates | [engine](../matchpulse/engine.py) | [completed-correction tests](../tests/test_demo.py) | Synthetic diagnostic estimates |
| Original gradients are analytical | [dense](../matchpulse/numerics.py), [temporal](../matchpulse/temporal.py) | Independent finite differences | Tiny CPU shapes |
| Learned parameters change | [training](../matchpulse/training.py) | Independent saved inference and loss replay | Three synthetic seeds |
| Censor likelihood preserves missing fees | [valuation](../matchpulse/valuation.py) | Derivative checks and undisclosed negative control | Does not solve selective disclosure |
| Eight forged bundles are rejected | [controls](../matchpulse/negative_controls.py) | Actual subprocess reports | Diagnostic workload only |
| 1.3653 ms backend pilot p95 | [campaign](../matchpulse/campaign.py) | Pilot LOAD.jsonl, independently recomputed | Executable source 93f5b0a |
| 25.4123 ms HTTP pilot p95 | [HTTP harness](../scripts/http-load.py) | Per-request HTTP.jsonl and STREAMS.json | Synthetic loopback, source d955af2 |
| Typed terminal uses real API | [terminal](../web/src/app.ts) | Browser replay, screenshots, real Go integration | Local diagnostic profile |
| Actual live integration | No acquired source | No actual live capture | **Blocked**, never claimed |
| Empirical actual-data model superiority | No acquired corpus | No qualifying actual campaign | **Blocked**, never claimed |

Pilot evidence is kept under ignored `evidence/` and included only in explicitly labeled diagnostic artifacts. New final-source campaigns retain their own commit and run IDs; pilot claims must never be silently relabeled with a later source identity.
