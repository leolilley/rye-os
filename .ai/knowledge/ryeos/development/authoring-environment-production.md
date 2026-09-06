<!-- ryeos:signed:2026-09-06T11:13:37Z:ea2d39403f788ed4d3ce691738f2b78474e6293407f35d0532bf88edd750507b:ZYM7TUZNX5apx9DMZaOTUJ5yA1iCHMPOoRW54aUup1CN5ujxZLz5Va3rWbe7hgpIou0djkENZWlA7Y9k7ugcAQ==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea -->
---
category: ryeos/development
tags: [development, authoring, external-content, production]
version: "1.0.2"
description: Finite production and qualification of the shared command environment.
---

# Authoring-environment production

The source-local namespace
`tools/ryeos/development/authoring-environment-production/` owns three finite,
ordinary Tool operations: `prepare`, `assemble` and `verify`. The adjacent `runtime`
executes their sealed Python source using an exact admitted interpreter.
It is not the runtime supplied to the final worker.

The exact Python executable discovers its own admitted standard library. Its
prefix is checked before loading verified source, and UTF-8 is selected through
argv. The runtime does not override protected `PYTHONHOME`, `PYTHONPATH` or
locale names. Missing runtime content fails qualification; it never permits
host path inheritance or a weaker node environment policy.

The selected `config:development/ryeos/authoring-environment-inputs` enumerates
every input's hash, bytes and mode, selected output members, exact relocation
targets and upstream provenance. Assembly and verification pin the same locator-free input
tree and interpreter. Inputs must be imported and bound to each Tool before
launch; the source-bearing input tree requires explicit large-content authority.
Execution has no acquisition, network, signing, binding or publication operation.

Input modes describe portable manifest identity, matching Lillux: an ordinary
regular file normalizes to `0755` if any executable bit is set, otherwise
`0644`. Immutable cache materializations may expose those bytes as `0555` or
`0444`. Preparation, assembly and utility-support checks use that input-only
projection without chmodding shared content. Exact hashes, sizes, complete
inventories and regular-file/bounds checks still apply. Newly produced trees
and receipts instead verify their exact physical permission bits.

## Flow through existing owners

1. Acquire the exact public inputs identified by the signed configuration using
   existing import/activation owners as applicable. Acquisition is separate
   from offline production; there is no turn-time package installer. Import
   and bind the prepared raw tree to `prepare`, then run that Tool in a fresh
   private retained workspace. It selects into the already-authored inventory,
   never learns or signs a replacement contract. Retain and import
   `products/authoring-prepared-inputs/tree`, then bind it to `assemble` and
   `verify`. A changed input selection requires explicit authoring/signing.
2. Admit a pinned private producer with retained result authority. Run
   `assemble` followed by `verify` in the same result lineage. Their filesystem
   ceiling is `captured_execution` and network authority is `isolated`.
3. Retain `products/authoring-environment` through the existing project result
   snapshot. Do not use shared-exclusive worker-child execution for this
   artifact-producing root: its output must survive terminal retention.
4. Import exact output members from that successful retained terminal. State
   selection applies the existing project floor/exclusions and verifies bytes;
   it does not reread the mutable producer workspace.
5. Bind the resulting content receipt to each exact Worker/Config consumer.
   Whole-source output and input trees use large content; the runtime subtree
   fits ordinary content. Neither checksum nor local artifact possession is
   consumer authorization.
6. Qualify the actual worker/environment pair, durable completion, fenced
   candidate retention and independent candidate validation.

`prepare` consumes the pinned raw tree at
`/ryeos/realizations/authoring-source-inputs` and resolves both the assembly-input
and `config:development/ryeos/authoring-utility-sources` contracts. Raw layout:
`bootstrap/` holds the exact binary/source archive pair; `workload/selected-package.tar.gz`
holds the selected resource package; `upstreams/` holds the named source/notice
files; `elf/` and the remaining `notices/` hold exact previously selected members.
Archive members are bounded, regular, exact-name selections; unselected entries
are not extracted. The operation verifies all 107 final hashes, sizes and physical modes
before advertising completion. It does not execute the acquired binaries,
contact a container daemon, use host PATH, acquire packages or manufacture pins.

`assemble` refuses existing output and staging paths. It checks all selected
inputs before running admitted upstream readelf/patchelf through their supplied
loader. Only declared dynamic members are relocated; static PIE remains
unchanged. Interpreter/library closure, executable modes and symbol ownership/
function coordinates are verified. Upstream ELF programs own interpretation;
there is no custom binary patcher.

`verify` independently reassembles into a separate private directory and compares
the complete file/mode/hash inventory. Both operations return compact output
coordinates and an inventory checksum, not embedded artifact bytes, fake CAS
receipts or publication authority. Their enclosing execution owns process-group
and resource limits. Failed staging is preserved for diagnosis and never bound.

## Artifact boundary

`environment/` contains 43 ordinary commands, a closed runtime for the selected
shell, and notices. `corresponding-sources/`, provenance and inventory accompany
the distributable output. Runtime binaries resolve at
`/ryeos/realizations/authoring-tools`. That fixed root requires enforced
isolation; it does not change ordinary live/filesystem execution or the node's
default backend policy.

The runtime does not include child compilers, project dependencies or a privileged
RyeOS client. No new package kind, solver, environment registry or manifest store
is introduced. The existing content manifest and target-local binding remain
the materialization/authority owners.

Artifact-only reproduction and an offline empty-root probe have passed.
Admitted preparation and single-root assembly also passed on 2026-09-06, with
no operator vault or network access. Exact completed-thread result imports
matched all four selected manifests: prepared inputs, runtime environment,
complete production output and shell file. Project HEAD remained unchanged.
`tests/e2e/authoring-environment/selection.json` retains the exact thread,
capsule, result and import coordinates, separately from the expected pins.

Independent admitted verification, final Worker/Config bindings, restart and
real hosted candidate qualification remain gates. The v7 source integration
replaces per-launch overlay creation with one original retained view and exact
transitive borrower freeze/cleanup fencing. Each isolated child attaches its
own clone of that template; the backing workspace is not remounted separately
for an inline child while its parent is alive. This cut also changes runtime
epoch 28 and launch metadata 30. The disposable qualification target still
needs the matching publication and scoped history retirement before an inline
assemble/verify graph can qualify. A standalone kernel proof or source-level
ownership test is not installed runtime integration or worker acceptance.
Direct Python execution is byte-reproduction evidence, not admitted Tool
execution evidence, and a successful assembly is not independent qualification.

## Utility-build dependency gate

`lib/utilities.py` owns the finite static-utility build recipe. It reuses the
existing Stage0 realization at `/ryeos/realizations/platform` for Zig rather
than creating another compiler platform. The source configuration's image
coordinate is historical provenance, not permission to access Docker or its
filesystem. The source archive's Zig copy supplies corresponding-source/license
evidence, not a second compiler installation.

Stage0 does not supply Make, a configure shell or their complete helper closure.
The build recipe therefore also requires a real, exact admitted build-support
inventory. That artifact is not yet selected or qualified, so there is no
runnable utility-build Tool or placeholder dependency. Supplying and qualifying
it, including nested script/interpreter paths, remains required before fresh
utility compilation can replace the historical binary/source inputs. Recipe
tests do not satisfy this gate. The original source archives remain preserved;
new retained build outputs carry upstream sources and the current recipe.
