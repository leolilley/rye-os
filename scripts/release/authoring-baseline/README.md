# Authoring input bootstrap and artifact probes

Final assembly and verification belong to the ordinary source-local Tools in
`.ai/tools/ryeos/development/authoring-environment-production/`. This directory
contains their bootstrap inputs and artifact-only probes, not a second RyeOS
production/publication authority. It introduces no execution kind, dispatcher,
environment registry or store.

`produce.py` builds the 41 static utility inputs; `verify.py` checks those
bootstrap archives. `prepare-assembly-inputs.py` selects them, exact workload
resources, upstream sources/notices and finite ELF-tool/runtime members from
the pinned image. The reviewed input inventory is the signed source-local
configuration consumed by both Tools. `fetch.py --assembly` acquires the exact
public inputs in `assembly-upstreams.json`; execution itself stays offline.

## Inventory and boundary

The bootstrap executable inventory is `sources[].programs` in `inputs.json`.
Final assembly adds exact upstream ripgrep and the patched zsh used by the
workload, giving 43 commands. There is no shell interpreter at `/bin/sh`:
execute shell scripts with admitted zsh, not a host shebang.

Git is supplied for `diff --no-index` and local scratch repository
init/add/status/diff/log operations. No remote transport, credential helper,
pager, editor, hooks, Git LFS, submodules, signing or scripted porcelain is
qualified. Disable system/global config and pagers in the signed environment.
Installing Git does not include `.git` in project snapshots, authorize a commit
or push, or replace RyeOS project-head/candidate authority.

No compiler, package manager, language runtime, host library search, privileged
RyeOS client or project-operation dependency is included. Tools with file
mutation or process-spawn capabilities are ordinary utilities, not a sandbox.
Do not infer network or filesystem isolation from this inventory.

## Runtime closure

The 41 bootstrap programs are static musl ELF. Upstream ripgrep is static PIE;
the patched shell has a closed glibc runtime, relocated during final assembly
to `/ryeos/realizations/authoring-tools`. The final environment requires that
fixed execution-runtime root under enforced captured-execution authority; it
is NOT a relocatable all-static archive. C locale and UTC are supported.
Localized catalogs, timezone databases, NSS account databases and optional
awk extension libraries are not included.

Inputs pin upstream URLs, archive SHA-256s, sizes, compiler and publisher image.
The publisher runs offline, builds with two jobs, normalizes archive metadata,
and produces a binary archive, per-file inventory and corresponding-source
archive. The source archive must accompany any binary redistribution. Preserve
the included upstream licenses/notices; this is not a license grant from RyeOS.

Build from the repository root (no RyeOS installation or node is involved):

```sh
authoring_source="$PWD/scripts/release/authoring-baseline"
authoring_cache="$(mktemp -d /tmp/ryeos-authoring-inputs.XXXXXXXX)"
authoring_work="$(mktemp -d /tmp/ryeos-authoring-build.XXXXXXXX)"
python3 "$authoring_source/fetch.py" --cache "$authoring_cache"
docker build --network=none --iidfile "$authoring_work/publisher-id" \
  -f "$authoring_source/Dockerfile.publisher" "$authoring_source"
docker run --rm --network=none --cpus=2 --memory=3g --pids-limit=512 \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$authoring_cache,dst=/inputs,readonly" \
  --mount "type=bind,src=$authoring_work,dst=/work" \
  "$(< "$authoring_work/publisher-id")" --cache /inputs --output /work/output
```

Use a fresh work directory and the same frozen publisher image for an
independent reproduction. Both the binary and corresponding-source archive
must match byte-for-byte. A build is not a public release; this procedure never
uploads an artifact. Preserve the output logs on failure.

## Qualification

`qualify.py --production <assembled-output> --inventory-sha256 <checksum>
--output <new-probe-directory>` verifies the complete inventory, constructs a
FROM-scratch image and runs the actual patched shell with descriptor-based
PATH. `probe.sh` exercises read, sed editing, search, diff/patch and scratch Git
in private tmpfs with no network or host libraries. The exact edited-file hash
is required, not just process success. This is artifact evidence, not RyeOS
admission/production, consumer binding, a hosted turn or candidate qualification.

`selection.json` records the independently reproduced selection and empty-root
result. Its expected RyeOS manifests are computed from the selected bytes using
the existing manifest recipe; they are NOT node import/binding receipts.
The complete input/source trees require large-content authority. Do not treat
the assembly input as ordinary `captured` content: its source archive alone
exceeds that tier's per-file limit.

The default Codex environment and projectless login remain minimal. A
development-facing environment selects the explicit `hosted-authoring` worker
and one runtime realization. Its worker-owned shell resource must also use the
relocated bytes; changing PATH alone cannot replace the workload's own shell.
Until a release archive has a real immutable delivery coordinate, provision
through the existing explicit external-content import and consumer binding;
do not invent a managed activation URL or widen trusted-consumer admission.
