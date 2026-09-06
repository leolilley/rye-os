<!-- ryeos:signed:2026-09-06T03:45:22Z:fdcaec3a2ef3253675b62046b777b576b237796e5597fdab932fc7371b748239:DC2uOxWnPzv2FFNoHZl/9taRrTcBUtpvZlSwKvj85CYNJht/T/mvs5//+u8rT2bhkP4rKYRgIOmNbaarb646Cw==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea -->
---
category: ryeos/development
tags: [development, authoring, external-content, production]
version: "1.0.0"
description: Finite production and qualification of the shared command environment.
---

# Authoring-environment production

The source-local namespace
`tools/ryeos/development/authoring-environment-production/` owns two finite,
ordinary Tool operations: `assemble` and `verify`. The adjacent `runtime`
executes their sealed Python source using an exact admitted interpreter.
It is not the runtime supplied to the final worker.

The selected `config:development/ryeos/authoring-environment-inputs` enumerates
every input's hash, bytes and mode, selected output members, exact relocation
targets and upstream provenance. Both Tools pin the same locator-free input
tree and interpreter. Inputs must be imported and bound to each Tool before
launch; the source-bearing input tree requires explicit large-content authority.
Execution has no acquisition, network, signing, binding or publication operation.

## Flow through existing owners

1. Bootstrap exact public inputs with the bounded helpers under
   `scripts/release/authoring-baseline/`. Review/sign a changed inventory and
   declaration; never silently learn new source identity at execution time.
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
`scripts/release/authoring-baseline/selection.json` records their exact selection
and distinguishes expected manifests from actual node receipts. Full admitted
production, import/bind/restart and real hosted candidate qualification must
still pass on a coherent signed generation. Bootstrap script success is not
Tool execution evidence.
