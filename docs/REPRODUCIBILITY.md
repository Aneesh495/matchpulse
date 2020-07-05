# Reproduce the bounded local profile

Use Python 3.13 or newer, Go 1.25, Node 24 and npm. Python and Go use only their standard libraries. TypeScript is locked at 5.9.3. No GPU, account key, network feed, paid resource, or downloaded checkpoint is needed for the authored replay.

```sh
make bootstrap
make doctor
make build
make test
make demo
make live-demo
```

Open `http://127.0.0.1:8777`. Select Finish to run event ingestion through full time, then Next event to add the separate later fictional sale. Inspect Luca Ferri for the save, Ivan Novak for the red card, Leo Marin for the overturned goal and final goal, and Adam Vale for the revised role. In the version selector, v28 is the provisional goal, v30 is its VAR retraction, and v37 is completed. Transfer terminal and CSV report 23 eligible synthetic estimates and keep the unused player unrated.

The service stores state in ignored `runtime/matchpulse.db`. Restart it to retain history and replay cursor. To start an additional independent demo, use a new database path: `./bin/matchpulse -db runtime/another-demo.db -addr 127.0.0.1:8778`. Do not delete an existing database to obtain a clean screenshot. The CLI `make demo` uses a separate memory database and has no persistent side effects.

```sh
make train RUN_ID=training-new-id
python3 -m matchpulse.verify_training evidence/training-new-id
make acceptance RUN_ID=engineering-new-id PROFILE=diagnostic
make verify EVIDENCE=evidence/engineering-new-id
make negative-controls EVIDENCE=evidence/engineering-new-id RUN_ID=controls-new-id
make valuation-audit INPUT=fixtures/official-deals.json
```

Every ID must be new. The verifier defaults to trusted current HEAD, not the bundle's declared source. Evidence made before a source edit must be checked from the exact source checkout. For final evidence, commit and push all executable files, make a clean checkout, run `npm ci`, then run the commands there. Supply `EXPECTED_COMMIT=<trusted-sha>` when needed. A report-only change still changes the default expected SHA, so use the original clean checkout.

Replay comparisons keep keys, ordering, types, integer counters, timestamps and source identities exact. Computed finite binary64 values allow at most two units in the last place across platform math libraries. Downloaded Linux evidence exposed a one-unit difference in two probability fields on macOS. Larger changes, nonfinite values and structural changes fail. This numerical portability rule changes no scientific or latency threshold.

Diagnostic archives include `MATCHPULSE_PACKAGE.json` for source identity and keep npm's `package.json` intact. The distinct basename supports case-insensitive filesystems. Package extraction checks must compare every tracked file byte-for-byte before rebuilding and starting the standalone service.

`make acceptance RUN_ID=full-new-id PROFILE=full` records blocked status and exits 2. It cannot pass without the actual-data campaign. `make data` and `make release` likewise fail clearly while acquisition and full acceptance are unavailable. `make replay SPEED=20` follows event-time delays and uses the same normalized ingestion path; a single delay over 60 seconds fails rather than sleep without a bound. `make ingest` ingests the authored packet without pacing. Operator-owned normalized JSONL can be supplied as `INPUT` after its fixture and source are seeded by the importer.
