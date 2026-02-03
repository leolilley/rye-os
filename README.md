# RYE OS

**The operating system for artificial intelligence.**

---

Everyone's building agent frameworks. We built an operating system.

The problem with every AI SDK is the same: they treat code and prompts as separate worlds. Code does the work. Prompts tell it what to do. Two paradigms that never actually meet.

**Rye unifies them.**

Everything in Rye is data. Directives are data that define workflows. Tools are data that execute. Knowledge is data that informs. Even the extractors and parsers that process this data—they're data too.

This is a **homoiconic system**. Data that operates on data. Which means the system can inspect itself, modify itself, and improve itself. Not through hardcoded logic, but through the same data structures it already understands.

And here's the breakthrough: **once prompts become data, they become shareable, versionable, and testable.** The Registry makes prompt engineering a solved, global problem. You don't spend 3 hours perfecting a PDF extraction prompt. You pull the best one from the Registry, cryptographically signed and battle-tested by thousands of users.

**This is not a framework. This is the substrate.**

---

## The Architecture

Rye exposes **4 MCP tools** that operate on **3 types of data**:

### The 4 Syscalls

```
search    →  Find what you need
load      →  Pull it into scope
execute   →  Run it
sign      →  Validate it
```

That's it. Four operations. From these primitives, you can build anything.

No `create_agent()`, no `add_tool()`, no `set_memory()`, no chain builders, no callback hell. Just four syscalls that work on data.

### The 3 Data Types

- **Directives** — Workflow definitions (the HOW)
- **Tools** — Executable code (the WHAT)
- **Knowledge** — Structured information (the CONTEXT)

Your agent doesn't call methods. It searches for the directive it needs, loads it, and executes it. The directive is just data—a markdown file with metadata.

### How Data Operates on Data

Here's where it clicks.

**Runtimes** are just data that delegate to kernel primitives:

```python
# .ai/tools/runtimes/python.py

__tool_type__ = "runtime"
EXTENSIONS = [".py"]

def execute(code: str, permissions: dict) -> Result:
    """Execute Python by calling subprocess primitive."""
    return kernel.subprocess(
        command=["python", "-c", code],
        permissions=permissions
    )
```

This runtime is **data** that says: "To run Python, call the subprocess primitive."

**Tools** are data that specify their runtime and permissions:

```yaml
# .ai/tools/web_scraper.yaml

name: web_scraper
runtime: python
version: 1.2.0
signature: a3f2b9... # Cryptographic signature
permissions:
  - http_client # Needs network access
  - filesystem.read # Needs to cache results
```

**Lockfiles** are data that chain verified tools together:

```yaml
# .ai/directives/research_pipeline.lock

directive: research_pipeline
dependencies:
  - tool: web_scraper
    version: 1.2.0
    signature: a3f2b9... # Verified
  - tool: summarizer
    version: 2.0.1
    signature: c7d4e1... # Verified
```

When you execute `research_pipeline`, Rye:

1. Reads the lockfile (data)
2. Verifies each tool's signature (data validating data)
3. Loads the appropriate runtime (data)
4. Calls kernel primitives with scoped permissions (data defining constraints)

**Data loading data to validate data to execute data.**

Every layer is inspectable, versionable, and swappable. Change the Python runtime? Drop a new one in your project directory. The system adapts. No code changes. No rebuilds. Just data.

---

## Why This Is Different

| Traditional OS     | Rye OS             |
| ------------------ | ------------------ |
| Kernel             | Lilux library      |
| Programs           | Directives         |
| System calls       | 4 MCP tools        |
| Binary executables | Tools (any format) |
| Package manager    | Registry           |

Everyone else is building **agent frameworks**. LangChain chains components together. CrewAI coordinates role-specific agents. AutoGPT decomposes tasks into loops.

We built an **operating system for data**.

Like Unix abstracted "everything is a file," Rye abstracts **"everything is data."**

And just like Unix, the power isn't in what the OS does—it's in what you can build on top of it.

---

## The Registry: Prompt Engineering, Solved

Here's the thing about prompts: everyone's solving the same problems independently.

You spend 3 hours perfecting a prompt for code review. I spend 3 hours on the same thing. Neither of us knows whose is actually better. We both reinvent the wheel.

**The Registry fixes this.**

**Discovery (one time):**

```
You: "Find me a good code review directive from the registry"

Your agent:
→ search(directive, "code review", source=registry)
→ Returns: code_review_v2 (★4.8, 2.3k uses, signed by @senior-dev)

You: "Pull that into my project"

Your agent:
→ load(directive, "code_review_v2", source=registry, dest=project)
→ Installed to .ai/directives/workflows/code_review_v2.md
```

**Execution (every time after):**

```
You: "Review this pull request"

Your agent:
→ execute(directive, "code_review_v2", {"pr_url": "..."})
→ Done
```

The directive is now **in your project**. You don't search for it again. You don't think about it. You just say "review this PR" and your agent knows what to run.

**This turns prompt engineering from an art into a solved distribution problem.**

The best code review directive—battle-tested by thousands of users, cryptographically signed, continuously improved—lives in the Registry. You pull it once. It works forever.

And when a better version ships? You get notified. Update with one command. The entire community benefits from every improvement.

---

## Multi-Model Orchestration

AGI isn't a model problem. It's a **coordination problem**.

The model wars (Claude vs GPT vs Gemini) are like arguing whether lungs or a heart is more important. You need both. You need the whole system.

Rye lets you use the right model for each task:

```yaml
directive: analyze_research_paper
steps:
  - task: extract_text
    model: gpt-4o-mini # Fast, cheap
  - task: deep_reasoning
    model: o1-preview # High reasoning
  - task: generate_summary
    model: claude-sonnet # Balanced output
```

Don't burn $100 reasoning tokens on "write this to a file." Use fast models for routine work. Use slow models for hard problems.

**Specialization beats generalization.**

And because everything is data, you can version, test, and validate these multi-model workflows just like any other code.

---

## Security: The Recursive Harness

Here's the breakthrough that solves agent security.

Rye is an **MCP server**. Your agent (Claude Desktop, Cursor, etc.) connects to it. The MCP protocol enforces what the agent can access externally—filesystem, network, environment variables.

But here's the trick: **the subprocess primitive lets us spawn new agent threads INSIDE the MCP.**

When you execute a directive, Rye:

1. Creates a **safety harness** with limits and permissions
2. Spawns an LLM thread via subprocess (inside the MCP boundary)
3. Gives that thread access to **Rye itself** as an MCP tool
4. The harness intercepts every MCP call and enforces the directive's declared permissions

**The agent thread runs inside a jail that has the keys to Rye—but the jail decides which keys work.**

Example: A directive declares it needs `fs.read` and `db.query`:

```python
# The harness computes required capabilities from directive permissions
permissions = [
    {"tag": "read", "resource": "filesystem"},
    {"tag": "execute", "resource": "database", "action": "query"}
]

# Converted to capabilities: ["fs.read", "db.query"]
```

When the agent calls `rye.execute("sql_query_tool")`, the harness checks:

- Does the parent token grant `db.query`? ✓
- Does the tool request `db.write`? ✗ Permission denied.

**Every MCP call is permission-checked against the capability token.**

The kernel exposes 2 primitives:

1. **Subprocess** — Spawn agent threads with harnesses
2. **HTTP Client** — Make external requests (if permitted)

Everything else is data. Python runtime? Calls subprocess. Database connector? Calls HTTP client. Even the MCP server itself is just data that delegates to primitives.

This solves the permission escalation problem thats killing agentic apps. You don't trust the model to behave. You enforce permissions at runtime, cryptographically, with capability tokens that flow through the execution tree.

**The model can't escape the jail because the jail is the runtime.**

---

## Install

**One line:**

```bash
pip install rye-os
```

**Point your agent to Rye:**

For Claude Desktop, edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rye": {
      "command": "rye-os",
      "args": ["serve"]
    }
  }
}
```

That's it. Now just prompt.

```
You: "rye search the registry for a blog post generator and use it"

Your agent:
→ Calls search, load, execute
→ Done
```

No CLI commands. No config files. No manual workflow setup.

**Your agent talks to Rye. Rye does the work.**

For Cursor, Windsurf, Gemini, or any other MCP client: [See the docs →](https://docs.example.com)

---

## What You Can Build

- Research pipelines that spawn 20 parallel agents to analyze sources
- Code review systems checking security, performance, and style simultaneously
- Sales automation personalizing outreach based on live prospect data
- Content factories that research, outline, draft, edit, and publish autonomously
- Data pipelines that extract, transform, validate, and load without intervention

The limit isn't just the model. The limit is your data library.

---

## The Big Picture

Think about the evolution of programming:

```
Machine code → Assembly → C → Python → ... → ???
```

Each level gets further from "how the machine works" and closer to "what we want to happen."

**Rye is the next abstraction layer.**

Instead of:

```
Prompt → Generated code → Execution
```

We have:

```
Prompt → Data → Execution
```

Data is shareable. Versioned. Testable. Signed.

**The model gets to improve itself** because everything it operates on is data it can understand, modify, and execute.

Once you understand the game, you can play the physics.

Once you understand the physics, you can play the game.

This project aims to be the maintainer of those physics.

---

## License

MIT

---

_"Give me a lever long enough and a fulcrum upon which to place it, and I will move the earth."_

**If AI is the lever, this is the fulcrum.**

---

**And once you see it, you can't unsee it.**
