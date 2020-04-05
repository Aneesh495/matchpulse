# ADR 010: Verify semantics against trusted source

Status: accepted for the local diagnostic profile.

Checksums detect accidental corruption but a forged summary can be rehashed. Self-declared source identity is circular.

Decision: Compare bundle source hashes with an externally expected Git commit and checkout. Independently recompute decisive quantities and replay exact saved inputs. Mutate semantically valid copies and require specific verifier rejections.

Consequence: The verifier covers the diagnostic workload only. It does not establish missing actual-data or expert-review gates. New production features require new frozen probes and negative controls.
