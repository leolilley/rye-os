# Authoring environment qualification

Production is owned by the ordinary Tools and adjacent libraries under
`.ai/tools/ryeos/development/authoring-environment-production/`; input contracts
live in `.ai/config/development/ryeos/`. This directory owns independent probes
and source-level regression tests, not an alternative producer or publisher.

Run the focused tests without a Rust build, daemon, credentials or model:

```sh
python3 -B -m unittest discover -s tests/e2e/authoring-environment -p 'test_*.py'
python3 -B -m unittest discover -s bundles/codex -p 'test_authoring_environment.py'
```

The utility-build tests are synthetic recipe/boundary tests. They do not prove
that the not-yet-provisioned build-support artifact closes every upstream
configure/Make subprocess. There is deliberately no executable build Tool until
that dependency and its confinement qualification exist.

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
on 2026-09-06. These are not independent admitted verification, final consumer
binding, a hosted turn or restart qualification. The cumulative `ryeos_production`
gate remains false until admitted verification passes as well.

Do not qualify inline assembly/verification against the current native backend:
the live parent and inline child would mount separate overlays over the same
upper/work directories. The generic workspace owner must first provide one
retained merged view and transitive borrower freeze/cleanup fencing. A passing
standalone kernel-mechanics probe does not establish those runtime contracts.

The complete source/input trees require large-content authority. The original
utility binary and corresponding-source archives remain exact historical inputs;
moving the production recipe does not claim that those archives were rebuilt.
