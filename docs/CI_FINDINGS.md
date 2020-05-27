# Retained hosted diagnostic miss

Executable source: `cdd47b8105c753d6eb5c79e0b7b9d48989c0d405`. The [hosted run](https://github.com/Aneesh495/matchpulse-football/actions/runs/43058268975) failed its concurrent HTTP diagnostic. This failure is preserved rather than replaced by the successful local run or the previous successful hosted run.

| Observation | Shared Linux result |
| --- | --- |
| Deliveries / concurrent callers | 592 / 16 |
| Reconnecting stream clients | 8 |
| HTTP roundtrip p50 | 24.9103 ms |
| HTTP roundtrip p95 | **255.9387 ms**, above the harness's existing 250 ms gate |
| HTTP roundtrip maximum | 426.7758 ms |
| Python processing p50 | 1.6681 ms |
| Python processing p95 | 7.5568 ms |
| Python processing maximum | 351.0168 ms |

Four rounds contained isolated processing stalls above 200 ms. Queued callers inherited those delays. Their event IDs were lineup-11, lineup-19, red-1 and sub-1. The timing pattern is consistent with commit/checkpoint or filesystem stalls, but the precise cause is not proven by the existing traces. SQLite documents that automatic checkpoints can occasionally lengthen commits in its [WAL performance discussion](https://sqlite.org/wal.html#performance_considerations).

The synchronization contract remains FULL. The single-connection writer is retained. No timing threshold, workload, data eligibility or stopping rule was reduced after the failure. The short local profile passed, while this shared Linux HTTP observation failed. G14 remains open. A later green workflow does not erase this observation or certify sustained production latency.

The failed run's raw HTTP.jsonl, STREAMS.json, database, final snapshots, environment, engineering bundle and verifier-control reports were downloaded and retained alongside the final local evidence. The artifact was named `local-diagnostic-cdd47b8105c753d6eb5c79e0b7b9d48989c0d405`, artifact ID 13872551137. The hosted source and local source are identical; their hardware and storage conditions differ.

Earlier hosted setup attempts also exposed unreachable Ubuntu package mirrors. Documentation now renders all DOT sources through pinned WebAssembly Graphviz installed from the package lock. That setup defect was fixed independently of the retained HTTP latency miss. Original failed setup logs remain in GitHub Actions.
