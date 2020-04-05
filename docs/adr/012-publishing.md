# ADR 012: Publish a diagnostic source project with explicit open gates

Status: accepted for the local diagnostic profile.

A runnable local product is useful, but research release status cannot be inferred from a green unit suite. The chosen Sites host does not run this Go/Python runtime.

Decision: Publish source and a local diagnostic package. Keep make release blocked while mandatory research and implementation gates remain incomplete. Document exact commands and source identities.

Consequence: A production hosted service, actual feed, large linked corpus and full acceptance release are not available. Private static hosting of an attractive disconnected interface would not satisfy the product flow.
