# Authoring environment qualification

## Hosted integration checkpoint — 2026-09-09

`hosted-worker-qualification.json` records partial installed two-node evidence,
not a passing development-loop gate. The disposable target used its dedicated
unprivileged runit service and configured-operator forwarding from a separate
source node. The primary node was not initialized, reset or restarted.

Pinned Codex read/edited the eight-file private fixture. Exact turn observation,
completion-fenced capture, frozen-candidate survival across daemon restart and
owner discard passed. Child formatting did not execute: after correcting the
signed shell environment, the nested command sandbox refused the restricted
broker connection with EPERM. Do not interpret completed turn/candidate facts
as successful project verification, promote these candidates, or claim Railway
or full-repository development acceptance.

The remaining connection must be admitted without general network access or
weakening broker authentication. The current PID-1 peer proof also needs native
nested-namespace qualification; it must not be replaced by acceptance of PID 0.
Shell here-document scratch usability remains unresolved. Existing operator-
driven Cargo and artifact evidence below does not establish these worker gates.

## Production and independent probes

Production is owned by the ordinary Tools and adjacent libraries under
`.ai/tools/ryeos/development/authoring-environment-production/`; input contracts
live in `.ai/config/development/ryeos/`. This directory owns independent probes
and source-level regression tests, not an alternative producer or publisher.

Run the focused tests without a Rust build, daemon, credentials or model:

```sh
python3 -B -m unittest discover -s tests/e2e/authoring-environment -p 'test_*.py'
python3 -B -m unittest discover -s bundles/codex -p 'test_authoring_environment.py'
```

The utility-build unit tests are synthetic recipe/boundary tests. Installed
captured/offline support assembly, nested subprocess qualification and a full
fresh utility build have separately passed; their exact execution coordinates
are in `build-support-qualification.json`. Assembly alone does not prove the
upstream configure/Make closure. The ordinary `build-utilities` entry reuses the
qualified recipe; its installed-execution gate is recorded separately below.

`build_support_probe.py` is an E2E Tool fixture. In a disposable copy of the
source project, materialize it beside the existing production runtime as
`build-support-probe.py` and sign that fixture. Capture the project using
`ryeos snapshot create <message>`, independently import/bind its exact Python,
support and Stage0 declarations to the fixture at that snapshot, then run:

```sh
ryeos execute tool:ryeos/development/authoring-environment-production/build-support-probe --current-head --no-operator-vault --async
```

The fixture verifies missing ambient shell/compiler/loader-cache paths, loads
every selected helper, builds a tiny static C program through nested Make and
shell, strips and runs it, and checks exact output. It uses the production
environment constructor and existing runtime bounds, with one Make job. It is
not a worker grant, full fresh utility build or hosted development acceptance.
`build-support-qualification.json` distinguishes these gates and retains exact
observed coordinates; it does not overwrite historical artifact evidence.

The nested probe passed on 2026-09-07 after an operator-approved target-only
open-file policy change from 1024 to 4096; its first failure is also retained.
It produced six selected result files and no retained compiler cache.

After that gate, `utility_build_probe.py` is the separate disposable E2E entry
for the sole `lib/utilities.py` fresh-build recipe. Materialize/sign it as
`utility-build-probe.py` beside that runtime and set its finite deadline using
project execution Config. Bind its four production dependencies at the captured
snapshot: Python, build support, Stage0 and source archives. The fifth exact
authoring-runtime input independently exercises fresh Git's final shell path;
it does not supply the freshly compiled utilities. The fixture extracts/builds
in isolated `/tmp`, retaining only products and bounded per-source logs.
The whole recipe passed on 2026-09-07, including fresh Git's shell alias. The
ordinary `build-utilities` Tool and this E2E entry share `utility_production.py`;
only the E2E entry adds the independent final-runtime probe. The installed Tool
entry also passed in `T-1632d8ec-05a1-793c-595a-339807f6104d`, retaining 80 files
and 92,435,329 bytes without publication. Independent retained-manifest comparison
matched all 41 executable entries, including bytes, modes and paths, against the
successful E2E build. Only the added shared-entry source and updated recipe/evidence
files differ; this is not whole-artifact equality. Historical utility archives and the
worker authoring environment remain separate evidence. This is operator-driven,
not worker/remote-loop qualification.

## Independent artifact probe

After producing an assembled output, run:

```sh
python3 tests/e2e/authoring-environment/qualify.py \
  --production <assembled-output> \
  --inventory-sha256 <independently-selected-inventory-checksum> \
  --output <new-probe-directory>
```

This checks the complete inventory, constructs a FROM-scratch image and invokes
the actual patched shell with descriptor-based PATH. `probe.sh` exercises read,
sed editing, search, diff/patch and scratch Git in private tmpfs with no network
or host libraries. The exact edited-file hash is required, not just exit zero.
Docker belongs to this independent probe only; no production Tool contacts it.

`selection.json` preserves the independently reproduced artifact selection,
empty-root evidence and separately identified admitted-production observations.
Expected manifests are computed from selected bytes; observed imports instead
come from exact completed-thread retained results through the normal CLI.
Admitted preparation, single-root assembly and all four manifest imports passed
on 2026-09-06. On 2026-09-07 the complete authoring graph executed assembly and
independent verification in the native backend's one retained shared view.
Both returned the selected inventory digest; the exact graph/capsule/result
coordinates are recorded in `selection.json`. The source HEAD did not advance
and no binding was published by the graph. `ryeos_production` is now qualified.

The owner/borrower integration uses one detached view, not separate overlays
over the same upper/work directories. The real graph result qualifies this
assembly/verification path, not the still-pending hosted worker/child loop,
restart, whole-repository Cargo operations or a remote development campaign.

The complete source/input trees require large-content authority. The original
utility binary and corresponding-source archives remain exact historical inputs;
moving the production recipe does not claim that those archives were rebuilt.
