# ADR 002: Keep occurrence and knowledge clocks separate

Status: accepted for the local diagnostic profile.

Sorting only by arrival creates incorrect match order. Sorting only by occurrence silently rewrites what a viewer could have known.

Decision: Every envelope stores occurrence, optional provider publication and actual receipt. Historical snapshots use received facts, then order the selected revisions by match clock.

Consequence: A current archive has unknown historical publication/revision clocks. The adapter preserves that limitation. Provider freshness cannot be inferred from service processing latency.
