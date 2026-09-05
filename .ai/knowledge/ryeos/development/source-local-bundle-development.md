<!-- ryeos:signed:2026-09-05T03:44:28Z:db20af25bb4944106eab7f07db910d1811ab3e9a0fcfce484930a87134fab1d4:/cmqxtrGHxIaeq0Hu6sdoqQcuhYGwPKlHzDPBbeBb8/Fp37yJNT0d7yxde4CtKnKK5gK8apcDFQx7+JuPHxJCA==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea -->
```yaml
category: ryeos/development
name: source-local-bundle-development
title: Source-Local Bundle Development
description: Source-local workflow, project-bundle, realization, and confinement contracts
entry_type: reference
version: "1.6.0"
```

# Source-Local Bundle Development

## Status

The original local command, state-root, signing, and bundle-smoke workflow is
implemented. The project-bundle and development-realization sections below
also record source-authored work that still has the explicit artifact,
runtime-root, signing, and qualification gates they name. They must not be read
as evidence that remote build/test execution is already available.

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

Repository-specific exclusions are authored in the existing
`.ai/config/execution/project-snapshot.yaml` contract. It excludes local
qualification artifacts, nested worktrees, local nodes and each active source
bundle's generated `bin`, `objects` and `refs` trees. These compose with node
patterns; `.gitignore` is not capture authority. RyeOS's current anchored-path
patterns are literal prefixes, so Git-style `bundles/*/...` patterns must not
be pasted into this policy. The focused source-policy test checks every bundle
in the development profile while retaining source, Tools and the public key
fixture. Preflight must still inspect the actual manifest for retired/untracked
directories before a real project is exposed to a worker.

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

## Repository project bundle

The repository-root `.ai` tree is also the source-local `ryeos` project
bundle. Its signed `.ai/manifest.yaml` is generated from
`.ai/manifest.source.yaml`; both are exact-file project sync surfaces. The
manifest declares only the `config`, `knowledge`, and `tool` kind dependencies
and no runtime authority.

Project AI surfaces have an explicit shape:

- a `file` surface admits exactly the named regular file and never descendants;
- a `directory` surface admits the named subtree but not a directory entry as
  project-manifest content; and
- apply replaces or deletes every materialized surface under one existing
  rollback window before advancing the deployed project ref.

Development configuration uses the generic
`.ai/config/development/<project-namespace>/` surface. The RyeOS repository
therefore uses `.ai/config/development/ryeos/`; the state/engine path contains
no `ryeos-next` or development-provider branch. Only that namespace, the root
manifests, and `.ai/tools/ryeos/development/` are unignored in this repository.
Unrelated root `.ai` content remains private/ignored unless deliberately added
to the registered project surface and Git contract.

The generated manifest and executable development items are signed by the
public development publisher fixture. That binds reproducible development
identity only. It grants no operator, node, release, deployment, vault,
publication, or remote authority.

## Development execution confinement

Core carries one self-contained `linux-lillux` isolation adapter under the
clean-cut isolation-adapter v4 protocol. The backend is available signed data,
not ambient host setup: bundle membership does not activate it and every
ordinary init profile remains explicitly disabled. The separately selectable
`development` init profile maps to the existing `full` bundle set and enables
the backend plus a finite workload-client node ceiling. It is a policy choice,
not a duplicate bundle distribution. A fresh local development node selects it
with `--bundle-set full --node-profile development`; replacing an existing
policy generation additionally requires the explicit
`--reset-node-policy-generation` decision. Hosted-worker profiles retain their
independently selected network policy.

The v4 plan carries a bounded, sorted collection of daemon-created target
channels and an explicit PID-namespace choice. Lillux owns namespace, mount,
pivot-root, seccomp, descriptor, pidfd/procfs and process-settle mechanics.
RyeOS layers own only typed authorities, exact adapter identity and signed
policy/data. Do not recreate those OS mechanics in an executor, daemon,
release script, project tool, Python bootstrap, or compiler-specific wrapper.
The same source-to-target descriptor mapping is enforced when isolation is
disabled, and the daemon side remains a typed Lillux byte-stream endpoint.
There is no raw Unix-socket conversion escape hatch.

Per-child filesystem and network denial are data driven. The signed Tool kind
projects composed `filesystem_authority` and `network_authority` into the
serialized execution plan. Development build/test items author
`captured_execution` and `isolated`; ordinary Tools use signed `node_policy`
defaults. Parent restrictions intersect irreversibly. The effective filesystem
ceiling is supplied before runtime compilation, so host-environment templates
and path mutations cannot capture ambient values before spawn filtering.
Execution-realization testimony records the same retained pair that launch
consumes. Neither restriction is silently accepted when isolation is disabled.
Generic dispatch never recognizes Cargo, Rust, Zig, Codex, or a project name.

Persistent sessions retain their signed protocol document, not merely its ref.
Admission intersects that protocol's workspace/network restrictions into the
plan before hashing. Recovery verifies the retained document against current
node trust and sealed identity; it never adopts a replacement descriptor from
the installed registry. Session testimony must not claim captured/isolated
authority simply because the process is a session.

Every external-content declaration and realized entry names a mandatory
`mount_root` and canonical relative `mount`. `project` targets the admitted
workspace; `execution_runtime` targets a strict child of the shared sandbox
namespace `/ryeos/realizations`. Allowed roots are signed kind/runtime data.
The Tool contract permits both; Worker, Config, Graph and launch-content
dependency contracts currently permit project roots only. Runtime mounts use
the existing descriptor-pinned read-only realization authority, reject mount
and workspace overlaps, and require enforced isolation. They never use the
disabled-mode project-copy path or enter project fold-back exclusions. Exact
realization-member command identity includes the root, path, manifest and
member digest through restart. No host path becomes portable authority.

Signed subprocess descriptors can project schema-validated scalar invocation
parameters through the existing bounded rye-expr/1 runtime template context,
for example one package name into one argv element. The value remains a single
argument; it is not reparsed as a command line. Prefer that ordinary data path
for finite project-tool selectors. Do not add a development argv builder,
shell/JSON shim, compiler-specific dispatcher, or command-multiplexer binary
when the existing Tool schema, config schema, and runtime template already
express the operation.

Tool subprocess protocol selection is likewise existing generic signed data.
Every executable Tool names one protocol admitted by the Tool kind's closed
allowlist. Development compiler/build/test tools select callback-free
`protocol:ryeos/core/opaque`, so their subprocess environment contains no
daemon callback or thread-auth bearer for build scripts to inherit. Tools that
need callbacks select `tool_callback` explicitly; command names never decide.

The native backend intentionally refuses aggregate resource isolation until a
typed delegated cgroup-v2 authority is carried to Lillux. Per-process rlimits
must not be represented as aggregate containment.

Initial confined build/test tools use the backend's existing private writable
`/tmp` for Cargo home, target output and compiler temporaries. Their exact
toolchain and dependency trees remain read-only realizations. Do not add a
durable runtime-view/cache authority merely to improve first-run performance;
such reuse requires an explicit lifecycle, recovery, quota and GC contract.

Multiple independent workers may consume the same immutable definitions,
toolchain/dependency identities and base project generation. Each owns its
writable workspace, command history and candidate. Identical content permits
storage reuse; it does not imply that every materializer already deduplicates
physical storage. Within one session, immutable child operations capture a
stable current generation and exclusive operations use its existing workspace
quiescence protocol. That protocol is not concurrent shared-directory editing
authority for unrelated workers. Cargo target directories remain private; there
is no implicit cross-worker writable build cache or automatic candidate merge.

RyeOS-specific environment composition belongs to this repository's development
configuration and Tools. Provider protocol and generic Codex integration remain
in the Codex bundle. Neither may supply node policy, target identity or
credential authority.

## Exact workload-client realization

The restricted workload client is an external realization, not a Core bundle
binary and not a file extracted from a runtime image. The official release's
single shared construction solve builds it as a fully static executable from
the exact release source and publishes a separate deterministic archive:

```text
ryeos-workload-client-<version>-x86_64-unknown-linux-gnu.tar.gz
```

The tree contains only `bin/ryeos`, the repository license, and canonical
`RYEOS-BUILD` testimony. The binary embeds the same testimony in a private ELF
section. Packaging and recovery verification require exact equality and bind
the explicit release version, full source revision, UTC build date,
source-date epoch, target, and release profile. An ordinary Cargo build is
marked `development` and cannot pass realization publication. Neither build
path consults Git to invent missing provenance.

The archive is portable content, not target authorization. A project-owned
worker environment or Tool first declares the real manifest digest produced
from this exact tree. Each target then uses the existing external-content
import and pinned-project consumer-binding path. Managed activation remains
restricted to trusted installed-bundle consumers; it is not widened for the
source-local project. Do not author a project environment, toolchain, or
dependency declaration with a placeholder digest. Those signed items land only
after the corresponding real tree has been produced and imported.

The verifier can publish the verified tree directly beneath an already-
admitted named-root directory. It stages beside the requested destination and
renames only the complete verified directory. It never provisions the named
root, changes node policy, or silently selects a fallback location:

```bash
scripts/release/verify-workload-client-realization.sh \
  --version "$version" \
  --source-revision "$source_revision" \
  --build-date "$build_date" \
  --source-date-epoch "$source_date_epoch" \
  --archive "$archive" \
  --checksum "$archive.sha256" \
  --materialize "$named_root/ryeos-workload-client-$version"
```

## Stage-0 platform payload

`.ai/config/development/ryeos/stage0-platform-x86_64-linux.yaml` is the
source-local signed input contract for the first compiler payload. It selects
the exact linux/amd64 publisher-image manifest, immutable dated Rust 1.95.0
component archives, Zig 0.15.2 archive, dated Rust manifest, byte bounds, hashes,
target and source-date epoch. It deliberately contains no output manifest
digest: that digest does not exist until the real tree is produced and
imported.

Stage-0 input schema v3 excludes the live Zig download catalog from acquisition.
That catalog is discovery evidence when selecting a version, not a reproducible
build input: unrelated nightly releases change its bytes. The authored versioned
archive URL, exact size and SHA-256 remain unchanged and mandatory. Never update
a catalog digest to whatever a build happens to download or consult a latest
catalog to replace a pinned archive. The old input schema is rejected, not
silently interpreted under the new contract.

`Dockerfile.development-realizations` runs the transparent publisher without a
package-manager step. The producer downloads only the selected upstream
archives, verifies exact sizes and digests, runs the upstream Rust component
installers into a private tree, extracts Zig into that same platform payload,
records the publisher/input/producer/program coordinates, inventories every
file, normalizes timestamps and emits one deterministic archive. Its signed
`image_member_*` rows additionally name exact canonical members of the pinned
publisher image: source path, destination member, mode, size and SHA-256.
These are explicit authoring sources, not execution-host discovery. They supply
the loader, glibc, libgcc, zlib, native linker support and license notices.
`runtime_alias_*` rows make regular copies of already verified tree members;
they do not introduce symlinks or custom executables. Zig is the native C
compiler/archiver; the upstream GCC driver and Rust LLD provide linking.
The producer explicitly retains the Rust archive-level license/copyright
notices that its component installer does not install. Installer logs,
uninstall scripts and installed-component manifests are excluded: they describe
a mutable installation and embed random authoring-directory paths. The verifier
requires the notices and rejects that bookkeeping in the immutable payload.
The retained input digest covers the canonical flat contract body, not its
replaceable signature header, so re-signing unchanged semantics does not alter
the produced tree.

The official GNU Rust host executables are dynamically linked. The separately
pinned upstream ELF authoring tool rewrites their interpreter and library paths
to `/ryeos/realizations/platform`, with default-library search disabled. The
shared publisher/verifier helper is bootstrap code, never a worker dispatcher.
It records every pre/post digest in `RYEOS-ELF-TRANSFORMS`, records selected image
members in `RYEOS-RUNTIME-SOURCES`, and inventories final interpreter/DT_NEEDED
edges in `RYEOS-RUNTIME-DEPENDENCIES`. The verifier resolves every such edge
inside the final tree and refuses undeclared executable scripts. Upstream
GDB/GDBGUI/LLDB launchers are omitted from the finite development operation set.

The selected ELF tool must preserve section order (`--no-sort`). Qualification
found that its ordinary section sorting changed libgcc symbol section
references despite a passing execution smoke test. Every transformed ELF is
therefore also checked for unchanged symbol ownership and function coordinates;
the tool's exit status alone is insufficient. This is an authoring check, not
permission to repair arbitrary worker executables.

The artifact class is `runtime_closed_platform_candidate`, not launch authority.
Its signed `execution_gate` is
`target_local_binding_and_isolated_acceptance_required`. The ordinary target
import/binding and actual Lillux execution proof remain mandatory. Generic
runtime-root support supplies the mount boundary, not implicit bytes. Ambient
host `/lib`, `/lib64`, `/usr` or `/bin`, undeclared image members, and custom
compiler wrappers remain forbidden. Produced build-script/test executables must
use this same loader/library closure through declared compiler arguments;
checking the compiler's own ELF edges alone does not prove its descendants.

The verifier checks the closed archive shape, complete retained tree
inventory, dated Rust-manifest hash, build testimony, executable dependency
evidence and signed bounds before optionally publishing one sibling-staged
directory. It does not clear the execution gate:

```bash
scripts/release/verify-development-toolchain-stage0.sh \
  --inputs .ai/config/development/ryeos/stage0-platform-x86_64-linux.yaml \
  --producer scripts/release/produce-development-toolchain-stage0.sh \
  --archive "$stage0_archive" \
  --checksum "$stage0_archive.sha256" \
  --materialize "$named_root/stage0-toolchain"
```

Qualifying Stage 0 runs the pinned publisher twice into distinct output
directories (and preferably distinct empty caches), then passes both archive /
checksum pairs to `test-development-toolchain-stage0.sh`. The test requires
byte-identical archives and checksums before applying the full verifier once; it
does not build or acquire anything itself. The tracked artifact tests consume
already-built archives, do not compile RyeOS, and never manufacture substitute
binaries. Artifact production and those tests remain explicit qualification
steps rather than release-time fallback logic.

## Import and target-local binding

Archive verification is not RyeOS launch authority. After materialization
beneath a node-policy named root, use the existing operator path to create the
ordinary content manifest:

```bash
ryeos external-content import \
  <named-root-id> <relative-tree> tree content <maximum-bytes>
```

The result supplies `staging_id`, `request_digest`, and the real
`manifest_hash`. Only then may the project Tool be authored with a locator-free
`mode: pinned` tree declaration naming that exact hash, an explicit permitted
`mount_root`, and a canonical relative `mount`. Sign the Tool, create the exact
project snapshot, and bind the staging
capability to that pinned project consumer:

```bash
ryeos external-content bind \
  <staging_id> <request_digest> <manifest_hash> \
  tool:ryeos/development/<tool> pinned_project \
  <project_snapshot_hash> <project-path>
```

The same sequence runs independently on every placement target. Portable
content may move through RyeOS object-closure transfer, but each node creates
its own operator-authorized binding. Managed activation remains restricted to
trusted installed-bundle consumers.

The Stage-0 dependency realization cannot be authored honestly before the
compiler payload, its exact runtime-root dependencies, and their real RyeOS
manifests are admitted. Its producer is the later signed project Tool that
invokes the exact admitted Cargo with `vendor --locked --versioned-dirs`; its
build descendants use only the resulting exact offline tree with `--locked
--frozen --offline`. A shell process using publisher-image Cargo, an ambient
Cargo home, or a checked-in placeholder manifest would create a competing
bootstrap authority, so none is included here.
