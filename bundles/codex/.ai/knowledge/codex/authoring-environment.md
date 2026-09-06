<!-- ryeos:signed:2026-09-06T03:45:22Z:9941091b316c6e65dd43dbe1b0b514420f87bd8d16c5740be2189b987ac9b7f2:+AlJ1CD0PAqVT9e0c/J0Jge09m6r+UGMi0JytibvSUCFR4RNBr8ah51Hjb8iBFV9g+8/l6xaOu1WFzgMsiseAQ==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea -->
---
category: codex
tags: [hosted-execution, environments, authoring, external-content]
version: "1.0.0"
description: >
  Explicit authoring worker and command environment, separate from child
  project-operation dependencies and restricted client authority.
---

# Authoring environment

Select `config:codex/environments/authoring` with
`worker:codex/hosted-authoring` for ordinary read/edit/search operations in a
private project. This uses the existing worker/environment composition. It adds
no package kind, environment registry, per-command wrapper or engine branch.

The default `worker:codex/hosted`, its environment and projectless login retain
their existing behavior. Their shared source closure includes the authoring
profile, so both workers' signed source digests change when that closure changes.

## Why the explicit worker variant

The pinned workload resolves its own zsh resource relative to its actual
executable. PATH does not replace that resource. The authoring variant therefore
selects the runtime-closed form of the exact upstream shell at the existing
resource location. Its signed profile adds only read access to
`/ryeos/realizations/authoring-tools`, alongside the existing baseline rules.
Routes, credentials and session schemas are shared with the default profile.

The environment owns the pinned runtime tree, executable search and ordinary
Git environment variables. Select the complete worker/environment pair; the
authoring worker is not a standalone replacement for the default worker.
Content bindings remain exact to each consumer. The default activation's
bindings do not authorize this new worker or environment.

## Available commands and runtime

The single admitted `authoring-tools/bin` search directory supplies 43 commands:

```text
awk basename cat chmod cmp cp cut date diff dirname env find git grep head
ln ls mkdir mktemp mv patch printf pwd readlink realpath rg rm rmdir sed
sha256sum sleep sort stat tail tee test timeout touch tr uniq wc xargs zsh
```

The utility baseline is static musl; ripgrep is upstream static PIE. The exact
upstream patched zsh uses a supplied glibc loader, libc, libm and libtinfo.
Assembly closes their interpreter/library paths at the fixed execution-runtime
root. There is no ambient host PATH or library substitute, turn-time package
acquisition, compiler, package manager or privileged RyeOS client.

Fixed execution-runtime mounts require an enforced isolation backend. This
profile selects the captured-execution filesystem ceiling; it does not enable
a backend or change default node isolation. RyeOS does not require its
Bubblewrap bundle. The upstream workload's existing internal sandbox resource
is unchanged and is not a RyeOS isolation-policy choice.

C locale and UTC are the supported baseline. Invoke shell scripts with admitted
zsh; a host `/bin/sh` or `/usr/bin/env` shebang is not a portable dependency.

Git is qualified for local inspection and scratch operations: `diff --no-index`,
`init --template=`, `add`, `status`, and `diff --cached`. System/global
configuration is disabled and the admitted cat is the pager. Remote helpers,
credentials, hooks, editors, Git LFS, submodules, signing and scripted porcelain
are not in the qualified closure. Missing helpers fail without host search.

Git availability does not add `.git` to project snapshots or authorize commits,
pushes or publication. A scratch index is an editing aid, not candidate authority.
Likewise, a finite utility inventory is not a sandbox or a permission grant.

## Production, import and binding

Source-local finite operations own final assembly and independent verification:

- `tool:ryeos/development/authoring-environment-production/assemble`
- `tool:ryeos/development/authoring-environment-production/verify`

They consume an exact pinned input tree and explicit Python runtime, with
isolated network authority. The completed output is
`products/authoring-environment` in the private project, not a cache, excluded
build directory or node store. Corresponding sources and notices accompany the
environment. Preserve them when redistributing binaries; source collection alone
is not a comprehensive redistribution-license review.

The source repository's bootstrap helpers acquire/check immutable inputs and
select upstream payloads. They do not replace RyeOS admission, Tool execution,
retained-result authority or target-local binding. No managed activation URL
is authored for an unpublished artifact.

After successful pinned production with retained output, use exact terminal
coordinates to import without reopening the producer workspace:

```text
ryeos external-content import-result <chain-root> <terminal-thread> \
  <result-snapshot> products/authoring-environment/environment tree content <bound>
```

Import the shell resource separately as a file from
`products/authoring-environment/environment/bin/zsh`. The full source-bearing
production and assembly-input tree require explicit `large_content` policy;
their source archive exceeds ordinary per-file content limits. Bounds and named
roots are measured target-local policy, not permissive bundle defaults.

Use the returned staging ID, request digest and manifest hash to bind the exact
consumer. All worker resources must also be provisioned for
`worker:codex/hosted-authoring`; equivalent bytes bound to `worker:codex/hosted`
are not sufficient. A project-owned environment needs the exact pinned project
generation; with the current bind command select its path using global
`--project`, not a positional `project_path` slot:

```text
ryeos --project <project-root> external-content bind \
  <staging-id> <request-digest> <manifest-hash> \
  config:project/environments/development pinned_project <snapshot-hash>
```

Installed consumers use `--no-project` and the `installed_bundle` scope. Import and
bind remain separate authority operations. Ordinary named-root filesystem
import remains available; retained-result import does not replace it.

## Qualification and remaining gates

The selected artifact has reproduced independently and passed an offline
empty-root probe for sed editing, search, diff/patch and scratch Git with
descriptor-based PATH and no host libraries. The source repository's
`scripts/release/authoring-baseline/selection.json` records expected manifests
and explicit qualification status. Expected hashes are not node receipts.

Before using a model, qualify the combined signed source/binary generation:
production/verification through RyeOS, retained-result import and exact consumer
bindings, fixed-runtime launch under enforced captured authority, shell/helper
behavior and restart. Generic admission is not an ELF dependency scanner; the
artifact probe and the actual workload path remain necessary.

Actual hosted acceptance must prove changed candidate bytes, the exact authored
command's durable completion, fenced termination and retained output. Independent
candidate qualification and authorized publication remain separate. A successful
turn or completion fence alone does not prove correct work.

Root workers receive authoring utilities and, where explicitly configured, the
restricted workload client. Child project-operation Tools own compiler/platform
and locked project dependencies. Do not move that closure into the root worker
or grant it ordinary daemon/vault/publication access to bypass child execution.
