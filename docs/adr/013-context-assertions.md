# ADR 013: Revisioned source context

Status: accepted.

Contract and availability evidence has both valid time and knowledge time. Flattening it onto a player row would let a later correction change historical research features without a trace. Automatically updating registrations from a fee observation would also invent facts about eligibility or contract termination.

Store immutable, source-bound context assertions with stable IDs and revisions. Resolve the latest known revision before filtering valid time. Preserve conflicting sources, withdrawals and unknown fields explicitly. Expose the same view through historical player inspection and bounded comparison. The operator owns source acquisition and canonical identity reconciliation.

The local importer and HTTP update route make the assertions usable. They do not acquire real injury, contract or registry evidence and do not promote those fields into a validated model. Direct imports require a stopped service; live updates use its serialized writer.
