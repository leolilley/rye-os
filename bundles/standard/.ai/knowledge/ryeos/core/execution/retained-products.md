<!-- ryeos:signed:2026-09-09T14:21:58Z:f04bec159daf218a96dce9d9c31ee036cbcef7a94c79d42c1683aaa374b87663:bh//dW8HcEQUuGaH4KK2Zm/Vu508pBOnPVIPve+xnnaI6vAs9D7RzMpk2q3JuOT/1LtQVdlKFtuuThC02kPfAA==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea -->
---
category: ryeos/core/execution
tags: [execution, products, external-content, authority]
version: "1.0.0"
description: Exact ownership and node-local provisioning boundaries for retained build products.
---

# Retained products and operator authority

A signed producer recipe names bounded products. Successful retained execution
supplies their exact bytes and provenance; node-signed product testimony records
that evidence. A signed consumer relationship and, where required, an independent
qualification determine whether a selected product can supply a consumer slot.
Possessing bytes or completing a producer does not itself authorize consumption.

## One owner across production and consumption

Product capture, lookup, retained-product staging, qualification, selection and
composition admit either the configured local operator or an authenticated,
origin-bound configured remote operator. Each service still requires its own
capability. A remote-node grant is not an operator grant, and a remote operator
without verified source-node forwarding proof is not admitted.

Producer, witness, verifier, selected product and execution retain their exact
operator identity. Node identity signs testimony; it does not substitute the
target's local operator for the caller. There is no cross-owner product sharing
or implicit delegation. Separate nodes need not share private signing keys.

The target local operator can provision a producer's exact literal input
bindings. A remote operator then runs the producer on that target, qualifies its
own products and selects them for its own consumer. This composes existing
authority; it does not turn node-local provisioning into a worker permission.

## Boundaries which remain local

Named-root filesystem import, ordinary binding (including selected-literal
binding), managed activation, and node policy administration remain local
configured-operator operations. Product composition uses its own verified
product path into ordinary staging and binding; it cannot import an arbitrary
host path or bind caller-invented manifests.

Product operations preserve node capacity limits, pinned consumer source,
complete slot selections, signed relationships, qualification evidence and
exact owner checks. Active bindings retain the authorizer and exact grant
digest. Revoking or changing that grant invalidates those bindings, including
bindings authorized by a remote operator. Recovery uses retained owner/origin
authority and revalidates the current grant.

Received product testimony is a separate same-operator contract. Trusting an
origin node does not transfer ownership or local qualification. A historical
witness from another operator must not be relabelled a local capture. Actual
large-object sidecar transfer remains separate from ordinary CAS-blob receipt.

## Evidence is not task success

Product qualification establishes the claims required by its signed relationship.
It does not qualify future worker edits. Worker command completion, frozen
candidate capture, independent candidate evaluation and explicit publication
remain separate authorities and qualification gates.
