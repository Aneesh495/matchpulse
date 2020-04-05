# ADR 003: Names nominate candidates and never merge people

Status: accepted for the local diagnostic profile.

Football names collide across ages, countries and vendor systems. Aggressive matching could attach a fee or red card to the wrong person.

Decision: Vendor aliases map to canonical people through valid and known-at intervals. A collision needs an explicit audited merge or split reason. Name normalization only constructs a deterministic candidate key.

Consequence: Human review and federation source reconciliation remain necessary. Candidate similarity is not confidence in identity. The demo uses deterministic fictional IDs and tests two people with the same name.
