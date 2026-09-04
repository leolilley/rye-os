<!-- ryeos:signed:2026-09-04T08:45:07Z:36011886825b9e9b51b9066b6569897d76a3b481c8a21d534192ac0ea0cd1234:BqEvSoAKx26a7GQDHJiYZiJIS1Ok7j73PsFk/a0gewSRfZMeKT1TQp4V+QQxECps2KsZYe26oU0iKKA5o4CCCw==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea -->
```yaml
category: ryeos/development
name: source-local-bundle-development
title: Source-Local Bundle Development
description: Implemented source-local command, state-root, signing, and bundle-smoke workflow
entry_type: reference
version: "1.1.1"
```

# Source-Local Bundle Development

## Status

This workflow is implemented. The entries below identify its supported
developer-facing contracts and their owning code.

- Command descriptors / local command help: routed without daemon alias
  parsing; project-aware tails auto-detect a cwd ancestor containing `.ai/`;
  `RYEOS_PROJECT_ROOT` / `RYEOS_PROJECT_PATH` are part of the runtime/env
  contract.
- **Runtime state-root override**: `ryeos execute <ref> --state-root /tmp/...`
  runs against the resolved project source while runtime state anchors under
  the override; both roots appear in the response's `execution` diagnostics.
  Live-fs only; a state root inside the project source is rejected.
- **Multi-item signing**: `ryeos sign` accepts a bounded set of changed
  bundle refs/paths in one invocation (`753d758e`), input hardened against
  escape (`c1751747`).
- **Bundle smoke command**: `ryeos bundle smoke` (service:bundle/smoke +
  command descriptor). Bundles declare a `smoke:` list in
  manifest.source.yaml; the service runs bundle preflight, then dispatches
  each entry as a normal synchronous wait-mode thread against the bundle source with state
  isolated under a temporary state root, and reports per-entry status,
  thread ids, and the state root (kept on failure or `keep_state`). See
  `crates/daemon/ryeos-api/src/handlers/bundle_smoke.rs` and
  `ryeos_bundle::manifest::SmokeDecl`.

## Project capture policy

The signed node `ingest_ignore` policy owns the complete conventional pattern
set. There are no engine-provided `.git`, build-directory, `.env`, or project-
specific defaults. RyeOS separately rejects its own identity, auth, vault,
signing-key, state, cache, bundle-registry lock, and pull-transaction paths as
a non-bypassable structural floor.

`.dev-keys/PUBLISHER_DEV.pem` is deliberately public, Git-tracked development
fixture material and remains part of a `full_project` snapshot. Its signature
does not represent owner, release, deployment, or publication authority.
Actual private operator/node/vault/release/deployment keys remain outside every
project generation.

This release makes `ingest_ignore` schema 2 a clean cut: it replaces the old
schema-1 `additional_patterns` extension with the complete `patterns` set.
An existing node therefore needs an explicit stopped-node generation
replacement during its first install of this version:

```bash
sudo scripts/pkg/install-local-direct.sh \
  --populate --all \
  --trust-source-publishers \
  --reset-node-policy-generation
```

The replacement selects the install's mapped signed profile and preserves
node/operator/vault identities, execution history, project heads, and all
non-policy state. Fresh nodes and nodes already on schema 2 omit the reset
flag. There is no schema-1 decoder or implicit migration.
