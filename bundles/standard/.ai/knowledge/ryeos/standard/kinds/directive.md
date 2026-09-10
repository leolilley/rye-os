---
category: ryeos/standard/kinds
tags: [kind, directive, llm, workflow]
version: "1.1.0"
description: Directive kind reference.
---

# Kind: directive

A directive authors executable intent for a model—not necessarily an enduring
assistant persona. The item defines work; each invocation is a distinct
admitted execution. Identity and authority come from the authenticated and
admitted execution contract, not a role named in the prompt.

A directive can make one bounded judgment or run a multi-turn tool loop. It
can be invoked directly or composed into a larger workflow. Neither use makes
it the owner of the campaign or grants it permission to accept its own result.
See [Directives](../directives/directives.md) for the design distinction.

Invariant: directives are markdown LLM workflows whose effective body, permissions, and context are composed before the directive runtime launches.

- Directory: `directives/`
- Format: `.md` via `parser:ryeos/core/markdown/directive`
- Composer: `handler:ryeos/core/extends-chain`
- Execution: delegates through runtime registry to `runtime:directive-runtime`
- Policy facts: `requires.capabilities.declared` becomes `effective_caps`
- Launch augmentation: composed context positions are rendered through the knowledge runtime before launch
- Hooks: authored `hooks` inherit or replace atomically; configured layers are captured before launch

Directive inheritance keeps the root body verbatim, narrows child permissions
against parent effective permissions, merges context blocks root-last by
position, and treats hook policy as one nearest complete list. After declared
augmentation, the daemon captures the effective hook plan, validates and seals
the full resolution, and the runtime recomputes its
`effective_definition_digest` before execution.
