# Stage-0 offline behavior fixture

This tiny, dependency-free Rust workspace exercises a build script, generated
source, a procedural macro, native C compilation/archive/linkage, a Rust test
and a child executable. Its C file is test input, not a RyeOS/compiler adapter.

After full artifact verification/materialization, run the exact publisher with
network disabled, the platform read-only at `/ryeos/realizations/platform`, and
this directory read-only at `/fixture`. Invoke `/bin/bash /fixture/probe.sh`.
It writes only to that disposable container's private `/tmp` and does not need
the repository, installed node, credentials, shared Cargo cache or host compiler.

This is authoring-side behavior evidence, **not Lillux isolation acceptance**.
The same cases must later pass through admitted project Tools and the actual
target-local binding before hosted development is qualified. Do not install
this probe as a worker-side command dispatcher or add it to release test gates.
