<!-- ryeos:signed:2026-09-06T04:55:43Z:52669f3919dc10972575e0ca06cf0d0aa321e44842db0f71a82e9755a9a521f5:otbS0ilk93CfGuOkXVCHxthB0QNT8WRjRrr+3lExXOtl5v06XjVgO1cKPrC/Zn1LDsEYx3Ln4I6l944dfAM+Dg==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea -->

---
category: ryeos/core/state
tags: [architecture, cas, state, truth, projection, sqlite]
version: "1.2.0"
description: >
  The three-tier truth model — CAS objects, signed refs, and the
  rebuildable SQLite projection. Content-addressed storage as the
  foundation of all state in the system.
---

# CAS Architecture

Rye OS uses content-addressed storage (CAS) as its single source of
truth. All state — events, snapshots, manifests, project files — flows
through CAS. Everything else is a derived view.

## The Three-Tier Truth Model

| Tier | Mutable? | Rebuildable? | Purpose |
|---|---|---|---|
| **CAS objects** | No (append-only) | N/A | Authoritative source of truth |
| **Signed refs** | Yes (one per head) | No | Entry points into the CAS graph |
| **SQLite projection** | Yes (derived) | Fully | Query performance |

The critical contract is **CAS-first, journaled writes**. Every chain-head
change records a durable pending transition before publishing its signed ref.
If projection work fails, the pending record remains and the repair worker
replays that named chain. Normal startup enumerates only this journal; it does
not sweep every historical signed head.

The selected projection has a generation-scoped instance identity and path,
named
`projection.<instance-id>.sqlite3`, chosen by
`state/recovery/thread-projection/generation.json`. If that selected generation
is absent, invalid, or from another schema epoch, bootstrap builds a fresh
instance by walking trusted signed heads, verifies it, and then atomically
publishes the generation pointer. The bootstrap lifecycle surface remains
responsive while that offline recovery runs.

### CAS Objects

Objects are stored under `state/objects/` using a two-level hex shard
layout: `objects/<ab>/<cd>/<sha256hash>.json`. Writes use
`lillux::atomic_write` (write-then-rename) for crash safety. Content is
serialized to canonical JSON and SHA-256 hashed before storage.

Every object — events, snapshots, manifests, chain state — is an
immutable JSON blob in CAS. The hash is the identity.

Executable source uses two ordinary typed CAS objects. A
`ryeos.source_closure_manifest` is a content-only, regular-file manifest whose
edges retain its file blobs. A separate `ryeos.effective_source_binding`
retains the owner, testimony, signed kind ceiling, executor policy, logical
mount identity, and an edge to that manifest. Launch and persistent-session
capsules retain the binding, so online and offline closure traversal and GC
reach the complete source tree without consulting a live project or bundle
path.

#### Canonical JSON Contract

RyeOS has one canonical encoding for CAS JSON. It is part of durable object
identity and signing, not a replaceable serializer setting:

- arrays retain their input order and objects contain no insignificant
  whitespace;
- object keys are ordered lexicographically by their decoded Unicode scalar
  values, before escaping;
- quotes, backslashes, and control characters use JSON escapes; every other
  non-ASCII scalar uses lowercase `\uXXXX`, with a UTF-16 surrogate pair for a
  supplementary scalar;
- numbers retain `serde_json::Number` rendering, including distinctions such
  as `0`, `0.0`, and `-0.0`;
- the content address is lowercase SHA-256 over those exact UTF-8 bytes.

Readers verify both the addressed byte hash and exact canonical encoding.
They do not repair, rewrite, or reinterpret an object in place. This contract
is deliberately not RFC 8785/JCS. A future encoding cannot silently replace
it: doing so would require an explicit new content-address domain and a
separately designed authority-preserving graph transition.

### Signed Refs

Refs are mutable pointers into the CAS graph. They live under
`state/refs/` and are updated atomically. Each ref points to exactly
one CAS object hash. Refs include:

- **Chain heads** — the latest chain state per root
- **Project heads** — the latest snapshot per project/principal
- **Bundle registrations** — signed records linking bundle names to paths

Refs are written by the node's signing key, so they are tamper-evident.

### SQLite Projection

The selected `projection.<instance-id>.sqlite3` is a materialized view of CAS
state, optimized for query performance. Only `Durable` events are indexed;
journal and ephemeral events are not projected.

The projection is **not authoritative** — it is a cache that can be
fully rebuilt from CAS at any time.

### Stable Operational State

`state/operational.sqlite3` owns records that cannot be reconstructed from
signed chain heads: CAS-entry attribution, admission-attestation lookup rows,
sync jobs and attempts, and provider-neutral credential-profile ownership,
lifecycle, confirmed account evidence, generation, and deletion tombstones.
Opaque provider credential bytes remain in the profile's node-private artifact
home. RuntimeDb retains a revisioned live projection so profile leases and
hosted-session transitions can share its transaction, but OperationalDb is the
only credential authority preserved across an explicit runtime-history schema
cutover. The cutover never decodes a predecessor runtime projection; it rebuilds
the exact-current projection from stable operational records. The operational
database is never selected through `generation.json`, copied, replaced, or
removed by projection rebuild or generation cleanup.
`state/operational.initialized` fails closed if an established operational
database later disappears.

## SQLite Schema Ownership

Every database in the system is stamped with a `PRAGMA application_id`:

| Database | ID | Hex | ASCII |
|---|---|---|---|
| `runtime.sqlite3` | `0x52594541` | `RYEA` | Runtime |
| `operational.sqlite3` | `0x52594f50` | `RYOP` | Stable operational state |
| `projection.<instance-id>.sqlite3` | `0x5259504a` | `RYPJ` | Projection generation |
| `scheduler.sqlite3` | `0x52595343` | `RYSC` | Scheduler projection |

On open, the system performs a four-step exhaustive check:

1. **Application ID match** — verifies the file was created by this
   daemon, not a foreign process
2. **Table set verification** — every expected table exists; no
   unexpected tables
3. **Column verification** — column count, names, types, primary keys,
   and NOT NULL constraints match exactly
4. **Index verification** — all expected indexes exist with correct
   uniqueness, columns, and tables; no unexpected indexes

Ownership failure never renames, archives, resets, or replaces the file. The
database class determines recovery:

- `runtime.sqlite3` is exact-current execution history. A predecessor table or
  embedded authority contract fails before row interpretation and requires the
  operator-confirmed thread-history/project-head reset; normal open never
  migrates or reinterprets it;
- `operational.sqlite3` is retained source-of-truth state. Deployed predecessor
  schemas advance only through explicit atomic forward migrations; it is never
  reset to activate a new schema;
- rebuildable stores (`projection.<instance-id>.sqlite3` and
  `scheduler.sqlite3`) evolve through their explicit reset-and-rebuild paths
  from durable source material.

An empty file (new database) triggers `init_owned()`, which runs the DDL and
stamps the application ID. A non-empty unstamped or foreign file fails closed
and remains untouched.

### Exact execution authority contracts

Thread snapshots, admitted launch capsules, runtime launch metadata, and
standalone persisted project authority are independent exact wire contracts.
Authoritative readers inspect the outer kind and numeric schema epoch before
typed deserialization, then validate the complete current shape and canonical
bytes. A nested predecessor shape therefore fails at its owning epoch instead
of being partially interpreted or reported as an incidental missing field.

RyeOS carries no compatibility decoder, alias, default, or in-place normalizer
for these execution contracts. When a clean-cut release changes them, startup
names the explicit offline reset command. That reset retires thread history
before recreating an empty exact-current runtime store. Project heads are
retired only when separately selected and explicitly confirmed;
it does not delete project source, bundles, vault values, or node identities.

## External-content receipts and shared bytes

An external-content import request identifies bounded byte acquisition under
node policy. It does not identify a consumer. Multiple Tools or pinned project
generations can legitimately reuse identical content through separate
target-node-authorized bindings.

Pinned-project binding identity commits to the exact generation, verified
publisher and pre-realization effective-program digest. Separately executed
source, when required by the signed program/executor contract, additionally
contributes its admitted source-closure projection and retained CAS edges.
A declarative exact-realization command has no such source tree: its current
binding records explicit null, never an invented empty closure. Omission is
invalid. Binding and launch use the same authority projection after source
admission; adding, removing or changing source evidence changes the binding
subject and cannot reuse a prior grant. Content use still requires the exact
active target-local binding and current authorizer.

The import service has two explicit sources. `source: filesystem` captures a
canonical member beneath a node-admitted named root. `source: retained_result`
selects a file or nonempty regular-file subtree from an exact successfully
completed execution's retained result snapshot. It requires the configured local
operator to own the exact chain root and thread; a snapshot hash alone grants
no access. Both produce the same staging receipt for separate consumer binding.

The CLI exposes these as:

```
ryeos external-content import <named-root> <path> <file|tree> <content|large_content> <maximum-bytes>
ryeos external-content import-result <chain-root> <thread> <result-snapshot> <path> <file|tree> <content|large_content> <maximum-bytes>
```

Use exact returned execution coordinates, not thread discovery or a mutable
workspace path. Retained import shares verified CAS file blobs and derives the
ordinary content manifest; files above the small-content ceiling use the existing
verified large-store ingest and chunk commitments. Producer/snapshot provenance
changes acquisition identity, not the resulting payload manifest. Current node
capture exclusions and all selected-tier limits still apply.

Project snapshots retain regular files and normalized executable modes, not
symlinks or empty directories. Retained tree import derives only directories
needed by retained files. It is not a lossless exporter of arbitrary filesystem
trees; use filesystem capture for richer trees, or a retained archive file when
the consumer explicitly handles that format. No source is silently substituted.

The staged manifest is a typed transitive GC root for both content stores. Binding
verifies that exact manifest and its complete closure, then stages the binding
root. Receipts need not enumerate every descendant. Import never publishes a
consumer binding or modifies the original workspace.

A binding retry validates its exact current signed binding and settles only
the presented principal-bound upload receipt. A fresh retry protects that
already-current binding root before completing its receipt; a receipt already
completed for another binding is refused. Do not treat every upload with the
same acquisition digest as a duplicate binding or settle another caller's
pending receipt. Unused stages remain protected until the existing explicit
maintenance policy permits their retirement. Content deduplication never
merges consumer authority or writable worker workspaces.

Synchronous external-content capture holds the existing shared CAS mutation
guard while writing bytes and verifying its completed manifest. Before returning
the import receipt, it durably stages that manifest root; GC follows its typed
edges. It does not enumerate every small blob again in the receipt. Explicit
large-object roots remain because binding verifies their import authority.
Binding likewise verifies the complete closure, stages the already-written
binding root, and publishes the signed binding head before receipt settlement.
An interrupted capture before root publication leaves unacknowledged bytes for
GC, not a durable root pointing to a missing manifest. Multi-request upload
acknowledgements retain their existing per-request staging contract.

Staging-root records have one symmetric bounded reader/writer envelope, separate
from small recovery journals. It accounts for object, blob and large-object
roots across their distinct stores; it does not expand node-policy admission.
Deterministic capacity refusal leaves the handle unchanged. A publication I/O
failure fences the handle, retaining its lock until drop, because rename may
have succeeded before sync failed. Normal reopen determines the actual durable
state; the old handle cannot continue using stale roots or undo settlement.

## Event Durability Tiers

Events have three tiers that control CAS storage and SQLite indexing:

| Tier | CAS Stored? | SQLite Indexed? | Survives Crash? | Use Case |
|---|---|---|---|---|
| `Durable` | Yes | Yes | Yes | State changes, artifacts, lifecycle |
| `Journal` | Yes | No | Yes | Audit trail, tool calls |
| `Ephemeral` | No | No | No | Token deltas, streaming logs |

The SQLite `events` table has a CHECK constraint that only accepts
`'durable'`:

```sql
durability TEXT NOT NULL CHECK (durability IN ('durable'))
```

Journal events are in CAS (recoverable on rebuild) but not queryable
through the projection. Ephemeral events are transient — lost on process
crash.

Events are assigned tiers by the runtime: high-frequency progressive
events (`token_delta`, `stream_snapshot`, `graph_foreach_iteration`)
are journal-only; all lifecycle and audit events are durable.

## CAS-First Write Contract

The system never writes to the projection without first writing to CAS and
publishing through the per-chain transition journal. The projection is a
**second-class citizen**:

- CAS/head succeeds, projection fails → the pending Set stays durable and the
  named-chain repair worker converges it
- Selected generation is deleted → bootstrap performs a verified full rebuild
  into a new selected instance before the application becomes Ready
- `INSERT OR IGNORE` in the projection prevents duplicate event indexing

`projection verify` is a fail-only, read-only inspection of the selected
generation. `projection rebuild` explicitly constructs and verifies a new
generation while the daemon is offline. Neither command runs as an automatic
history-sized sweep on a normal current-generation boot.

This is an event sourcing pattern where the events live in a
content-addressed graph with hash-linked chains, and the projection is
just a materialized view.

## Object Services

The CAS layer is exposed through three service endpoints:

| Service | Endpoint | Purpose |
|---|---|---|
| `objects/has` | `POST /objects/has` | Check whether hashes exist |
| `objects/put` | `POST /objects/put` | Write content to CAS |
| `objects/get` | `POST /objects/get` | Fetch content by hash |

All three are fail-closed: `objects/get` aborts if any requested hash
is missing rather than returning partial results. Remote push/pull,
pushed-head execution, and remote bundle install all depend on these
services.

## Garbage Collection

GC operates on the CAS layer in two phases:

1. **Compact** (opt-in): prunes snapshot DAGs per project according to
   `RetentionPolicy`, rewrites parent hashes, advances HEAD refs
2. **Sweep** (always): mark-and-sweep across all sharded directories,
   deletes unreachable objects and blobs, cleans empty shard directories

See [maintenance-gc](../services/maintenance-gc.md) for details.
