# RYE OS

> **EXPERIMENTAL**: This project is under active development. Features are subject to change.

> _"In Linux, everything is a file. In RYE, everything is data."_

**The last MCP your agent will ever need.**

**RYE** (RYE Your Execution) is an MCP (Model Context Protocol) server that treats AI workflows, tools, and knowledge as structured data. Not code. Not prompts. Data.

Built on **Lilux**—a microkernel providing pure execution primitives—RYE solves the fundamental interoperability problem in AI: **workflows, tools and context are trapped in projects, disconnected across agents**. While Claude Desktop, Cursor, Windsurf, and others can all understand "run a security scan," the workflow that defines _how_ to scan—the tools, the steps, the knowledge—is locked in each environment. You rebuild it for every project. You can't modify it centrally. You can't share it across your team.

**RYE fixes this.**

One security scan workflow. Used across all agents. Modified in one place. Instantly available everywhere.

---

## The Problem: Fragmentation

AI agents are powerful, but workflows are scattered. Every project rebuilds the same security scan. Every team reinvents the same deployment pipeline. Workflows live in one environment, stuck there.

- **No portability**: Your security scan in Project A doesn't exist in Project B
- **No consistency**: Each project implements "security scan" differently
- **No sharing**: Your team's best practices never leave the repo where they were born
- **No discoverability**: You rebuild what already exists somewhere else

**Solve once, solve everywhere.** This is RYE's promise.

---

## The Physics of AI Prompting

> _"Once you understand the physics, then you can play the game. RYE aims to be the maintainer of physics."_

Every AI system has the same underlying mechanics:

- Tools need to be discovered and executed
- Workflows need to be orchestrated
- Permissions need to be enforced
- Costs need to be tracked
- State needs to be managed

RYE encodes these fundamentals as **data**, not implementation. The physics are consistent. Only the execution environment changes.

---

## Data-Driven Everything

RYE treats three types of items as structured data:

### 1. Directives (XML Workflows)

Declarative workflows stored as XML-embedded markdown:

```xml
<directive name="security_scan" version="1.0.0">
  <metadata>
    <description>Scan codebase for vulnerabilities</description>
    <category>security</category>
  </metadata>

  <process>
    <step name="analyze">
      <execute item_type="tool" item_id="security/analyzer">
        <param name="target" value="src/" />
      </execute>
    </step>
  </process>
</directive>
```

### 2. Tools (Executable Code)

Python, JavaScript, YAML, or Bash scripts with metadata headers:

```python
__version__ = "1.0.0"
__executor_id__ = "python_runtime"
__tool_type__ = "security"

async def main(**kwargs):
    target = kwargs.get('target')
    # Analysis logic
    return {"vulnerabilities": []}
```

### 3. Knowledge (Patterns)

Structured learnings with YAML frontmatter:

```markdown
---
id: python-async-patterns
category: patterns/async
tags: [python, async]
---

# Python Async Best Practices

## When to Use Async

- I/O-bound operations
- Network requests
```

All three live in your project's `.ai/` directory:

```
.ai/
├── directives/     # XML workflows
├── tools/          # Executable scripts
└── knowledge/      # Patterns & learnings
```

### Content Integrity: Everything Has a Hash

Every directive, tool, and knowledge item is cryptographically signed:

```markdown
<!-- rye:validated:2026-02-10T02:00:00Z:a1b2c3d4... -->

# Directive Name
```

**Why this matters:**

1. **Verifiability**: You know exactly what code is running
2. **Tamper Detection**: Any modification invalidates the signature
3. **Reproducibility**: Same content always produces same hash
4. **Trust**: Registry items are signed by their authors + registry

**How it works:**

- SHA256 hash of canonical JSON (sorted keys, no whitespace)
- Signatures embedded in file headers
- Validation before every execution
- Registry adds provenance: `|registry@username`

This means when you pull a directive from the registry, you can verify it hasn't been modified since signing. When your agent executes a tool, it validates the hash matches the expected value. Content is addressed by its hash—tamper-proof and verifiable.

---

## The Execution Layer: Lilux Primitives

Every tool in RYE ultimately runs through **two execution primitives** provided by Lilux:

### 1. SubprocessPrimitive

Executes shell commands in isolated environments:

- Process isolation
- Environment variable injection
- Timeout and signal handling
- Output capture (stdout/stderr)

### 2. HttpClientPrimitive

Makes HTTP requests with retry logic:

- Authentication header management
- Timeout and retry configuration
- Response streaming
- Error handling

**That's it.** All tool execution reduces to these two primitives.

### The Tool Chain

RYE builds a recursive chain for every tool execution:

```
Your Tool (e.g., security/analyzer.py)
    ↓ __executor_id__ = "python_runtime"
Python Runtime
    ↓ __executor_id__ = "subprocess"
Subprocess Primitive
    ↓ executor_id = None (is primitive)
Execute via Lilux
```

The chain resolves recursively: each layer's `__executor_id__` points to the next layer until reaching a primitive (where `executor_id = None`). Common chain lengths are 2-4 layers, but there's no fixed limit.

Each layer validates before passing down. The chain ensures compatibility between tool requirements and execution environment.

### Lockfiles for Determinism

Every resolved chain generates a lockfile:

```json
{
  "lockfile_version": 1,
  "root": {
    "tool_id": "security/analyzer",
    "version": "1.0.0",
    "integrity": "sha256:a1b2c3..."
  },
  "resolved_chain": [
    { "tool_id": "security/analyzer", "integrity": "sha256:a1b2c3..." },
    { "tool_id": "python_runtime", "integrity": "sha256:d4e5f6..." },
    { "tool_id": "subprocess", "integrity": "sha256:g7h8i9..." }
  ]
}
```

**Why lockfiles matter:**

- **Reproducibility**: Same chain every time
- **Security**: Verify each layer hasn't changed
- **Caching**: Skip resolution if lockfile matches
- **Audit**: Complete execution trace

Lockfiles are stored in `USER_SPACE/.ai/lockfiles/` and committed to version control. When you share your project, others get the exact same tool chain.

---

## Universal MCP Discovery

RYE doesn't just provide tools—it **absorbs other MCP servers** and turns them into data-driven tools.

Connect to any MCP server (stdio, HTTP, or SSE), discover its tools, and instantly use them through RYE's unified interface:

**Execute directives via natural language:**

```
"rye discover mcp server https://api.context7.com/mcp"
"rye list mcp servers"
"rye execute mcp context7 search for authentication patterns"
```

These natural language commands map to tool calls through your llm:

| You Say                      | RYE Tool Call                                                               |
| ---------------------------- | --------------------------------------------------------------------------- |
| `discover mcp server X`      | `execute(item_type="tool", item_id="rye/mcp/manager", action="add", url=X)` |
| `list mcp servers`           | `execute(item_type="tool", item_id="rye/mcp/manager", action="list")`       |
| `execute mcp X search for Y` | `execute(item_type="tool", item_id="mcp/X/search", query=Y)`                |

**Example: Mapping "rye discover mcp server https://api.context7.com/mcp"**

The LLM translates this to:

```json
{
  "item_type": "tool",
  "item_id": "rye/mcp/manager",
  "action": "add",
  "name": "context7",
  "transport": "http",
  "url": "https://api.context7.com/mcp"
}
```

### How It Works

1. **Discovery**: RYE connects to external MCP servers via stdio, HTTP (Streamable), or SSE
2. **Conversion**: Each discovered tool becomes a YAML configuration in `.ai/tools/mcp/`
3. **Data-Driven Execution**: External tools are executed through RYE's chain resolution
4. **Environment Integration**: Auto-loads `.env` files for API keys and configuration

```
.ai/tools/mcp/
├── servers/
│   └── context7.yaml          # Server configuration
└── context7/
    ├── search.yaml            # Discovered tool configs
    ├── resolve.yaml
    └── get-library.yaml
```

### Customize Your Command Language

Want your agent to understand your own phrasing? Add a command dispatch table to your `AGENTS.md`:

```markdown
## COMMAND DISPATCH TABLE

| User Says                    | Run Directive          | With Inputs |
| ---------------------------- | ---------------------- | ----------- |
| `connect to X mcp`           | `rye/mcp/discover`     | `url=X`     |
| `what mcp servers do i have` | `rye/mcp/list_servers` | none        |
| `search X using mcp Y`       | `mcp/Y/search`         | `query=X`   |
```

Now your agent understands _your_ language while still executing RYE directives.

### Universal Compatibility

- **stdio**: Local CLI tools (e.g., custom scripts)
- **HTTP**: Remote services with Streamable HTTP transport
- **SSE**: Legacy SSE transport support

Environment variables are automatically resolved from:

- User space: `USER_SPACE/.env` (default: `~/.ai/.env`)
- Project: `./.ai/.env`, `./.env`, `./.env.local`

This means RYE becomes a **universal MCP client**. One connection point. Every MCP server accessible as data-driven tools.

---

## The Registry: Shared Intelligence

The registry is a centralized, cryptographically-signed store:

- **Discovery**: Find solutions others have built
- **Validation**: Items are SHA256-hashed and signed
- **Versioning**: Track changes and updates
- **Sharing**: Push your workflows, pull others

Identity model: `namespace/category/name`

The registry is just another data-driven tool with actions:

**Via natural language:**

```
"Search the registry for security scanner directive"
"Pull leolilley/security/scanner from registry"
"Push my security/scanner tool to registry"
```

**These map to registry tool calls:**

| You Say                 | RYE Tool Call                                                                            |
| ----------------------- | ---------------------------------------------------------------------------------------- |
| `search registry for X` | `execute(item_type="tool", item_id="rye/registry/registry", action="search", query=X)`   |
| `pull X from registry`  | `execute(item_type="tool", item_id="rye/registry/registry", action="pull", item_id=X)`   |
| `push X to registry`    | `execute(item_type="tool", item_id="rye/registry/registry", action="push", item_path=X)` |

**Example: Searching the registry**

```json
{
  "item_type": "tool",
  "item_id": "rye/registry/registry",
  "action": "search",
  "query": "security scanner",
  "item_type": "directive"
}
```

ECDH encryption for auth. Server-side validation. Local integrity verification.

---

## LLM Threads Inside the MCP

RYE doesn't just orchestrate—it **runs agents inside the MCP**.

Spawn isolated LLM threads with scoped permissions:

```xml
<directive name="parallel_analysis" version="1.0.0">
  <metadata>
    <description>Run security analysis in parallel using spawned threads</description>
    <category>security</category>
    <author>rye</author>
    <model tier="haiku" id="claude-3-5-haiku-20241022">Fast analysis with fallback</model>
    <limits max_turns="8" max_tokens="4096" />
    <permissions>
      <execute>
        <tool>rye.agent.threads.spawn_thread</tool>
        <tool>rye.file-system.fs_read</tool>
      </execute>
      <search>
        <directive>security/*</directive>
      </search>
      <load>
        <directive>*</directive>
      </load>
    </permissions>
    <cost>
      <context estimated_usage="medium" turns="8" spawn_threshold="3">
        4096
      </context>
      <duration>300</duration>
      <spend currency="USD">5.00</spend>
    </cost>
    <hooks>
      <hook>
        <when>cost.current > cost.limit * 0.8</when>
        <execute item_type="directive">notify-cost-threshold</execute>
      </hook>
      <hook>
        <when>error.type == "permission_denied"</when>
        <execute item_type="directive">request-elevated-permissions</execute>
        <inputs>
          <requested_resource>${error.resource}</requested_resource>
        </inputs>
      </hook>
    </hooks>
  </metadata>

  <process>
    <step name="spawn_security">
      <execute item_type="tool" item_id="rye.agent.threads.spawn_thread">
        <param name="thread_id" value="security-check" />
        <param name="directive_name" value="security_scanner" />
      </execute>
    </step>
  </process>
</directive>
```

### Safety Harness

Every thread runs with:

- **Cost tracking**: tokens, turns, duration, spend
- **Permission enforcement**: CapabilityToken validation
- **Hook-based error handling**: retry, skip, fail, abort
- **Checkpoint control**: pause, resume, inspect

### Hooks: Conditional Actions

Hooks let you respond to events during execution:

```xml
<hooks>
  <hook>
    <when>cost.current > cost.limit * 0.8</when>
    <execute item_type="directive">notify-cost-threshold</execute>
  </hook>
  <hook>
    <when>error.type == "permission_denied"</when>
    <execute item_type="directive">request-elevated-permissions</execute>
  </hook>
</hooks>
```

Available context: `cost.current`, `cost.limit`, `error.type`, `loop_count`, `directive.name`

---

## Security: Capability-Based Permissions

RYE uses a unified capability system where permissions declared in directives become runtime capability tokens.

### Declaring Permissions

Permissions are declared hierarchically in directive XML:

```xml
<permissions>
  <execute>
    <tool>rye.file-system.fs_read</tool>
    <tool>security/*</tool>
  </execute>
  <search>
    <directive>workflows/*</directive>
  </search>
  <load>
    <tool>rye.shell.*</tool>
  </load>
</permissions>
```

When a directive runs, its permissions are converted to capability strings:

- `rye.execute.tool.rye.file-system.fs_read`
- `rye.execute.tool.security.*`
- `rye.search.directive.workflows.*`
- `rye.load.tool.rye.shell.*`

### Runtime Enforcement

These capabilities become a **CapabilityToken** for the thread:

```python
# Token created from directive permissions
cap_token = CapabilityToken(
    capabilities={
        "rye.execute.tool.rye.file-system.fs_read",
        "rye.execute.tool.security.*",
        "rye.search.directive.workflows.*"
    },
    thread_id="security-check"
)

# Every tool call validates against the token
# Violations raise PermissionDenied
```

### Thread Isolation

Each spawned agent gets its own capability token derived from its directive's permissions, plus:

- Cost budget (tokens, turns, duration, spend)
- Resource limits
- Scoped capability access

### Integrity Verification

SHA256 hashes with canonical JSON serialization:

- Deterministic hashing (sorted keys, no whitespace)
- Signature verification on registry pull
- Content tampering detection

---

## RYE vs Traditional Agent SDKs

Traditional agent SDKs (like LangChain, OpenAI Assistants, CrewAI) provide:

- **Runtime-driven execution**: Imperative code with hardcoded logic
- **Framework coupling**: Tools only work within that framework
- **Implicit security**: Policy filtering baked into runtime
- **Non-portable**: Workflows don't transfer across environments

**RYE is different.**

| Aspect                  | Traditional SDKs         | RYE                                      |
| ----------------------- | ------------------------ | ---------------------------------------- |
| **Workflow Definition** | Code with decorators     | XML data files                           |
| **Tool Discovery**      | Import and register      | Filesystem scan                          |
| **Execution**           | Direct function calls    | Chain-based primitive resolution         |
| **Security**            | Runtime policy filtering | Capability tokens + declared permissions |
| **Portability**         | Locked to framework      | Works in any MCP environment             |
| **Sharing**             | Package registries       | Cryptographically-signed data registry   |
| **Extensibility**       | Write code + rebuild     | Drop file in `.ai/tools/`                |

### The Key Difference

**Traditional SDK**: Tools are TypeScript/Python functions registered at runtime. Security is layered policy filtering. Execution is direct.

**RYE**: Tools are data files with metadata headers. Security is capability-based with explicit permissions declared in XML. Execution builds a layered chain (tool → runtime → primitive) validated before running.

### Why It Matters

With traditional SDKs, building an agent means:

1. Writing framework-specific code
2. Managing complex policy configurations
3. Rebuilding for every change
4. Locking yourself into one ecosystem

With RYE:

1. Write XML workflows and executable tools
2. Declare permissions explicitly
3. Drop files to add functionality
4. Use the same workflows in Claude Desktop, Cursor, Windsurf, or any MCP client

### Deployment: HTTP Server vs. Agent Runtime

**Traditional SDK Deployment:**

Traditional SDKs require embedding their agent runtime into your application:

```python
# LangChain/CrewAI - Runtime coupled with your app
from crewai import Agent, Task, Crew

agent = Agent(
    role='Security Analyst',
    goal='Scan codebase for vulnerabilities',
    tools=[security_scanner_tool]  # Must import/register tools
)

task = Task(
    description='Scan src/ for vulnerabilities',
    agent=agent
)

crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff()  # Blocking, stateful runtime
```

Problems:

- Runtime bloat in your application
- Hard to scale horizontally
- State management complexity
- Must rebuild/redeploy to update workflows

**RYE Deployment:**

RYE workflows run via **deterministic tool calls**. Wrap the MCP in a simple HTTP server:

```python
# http_server.py - Minimal FastAPI wrapper
from fastapi import FastAPI
from rye.server import rye_mcp_server

app = FastAPI()

@app.post("/api/security/scan")
async def security_scan(repo_url: str):
    # Spawn a directive thread via MCP
    result = await rye_mcp_server.execute(
        item_type="directive",
        item_id="security/scan",
        inputs={"repo_url": repo_url}
    )
    return result

@app.post("/api/deploy")
async def deploy(environment: str, version: str):
    result = await rye_mcp_server.execute(
        item_type="directive",
        item_id="deployment/pipeline",
        inputs={"env": environment, "version": version}
    )
    return result
```

**Advantages:**

1. **Stateless**: Each request spawns a fresh directive thread
2. **Scalable**: Horizontal scaling with load balancers
3. **Observable**: Each execution is a deterministic tool call with full traceability
4. **Hot-swappable**: Update `.ai/directives/` files without redeploying
5. **Language-agnostic**: HTTP API works with any client

**Example: Kubernetes Deployment**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rye-api
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: rye-api
          image: myapp/rye-api:latest
          volumeMounts:
            - name: directives
              mountPath: /app/.ai/directives
      volumes:
        - name: directives
          configMap:
            name: workflow-directives
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: workflow-directives
data:
  security/scan.md: |
    <!-- directive content -->
  deployment/pipeline.md: |
    <!-- directive content -->
```

Update workflows by updating the ConfigMap. No container rebuilds. No downtime.

**Traditional SDK**: Runtime is the agent. Stateful. Complex scaling.

**RYE**: Runtime is an HTTP API. Stateless. Simple scaling. Workflows are data.

---

**Note:** RYE is not yet published to PyPI. Install from source:

```bash
git clone https://github.com/leolilley/rye-os.git
cd rye-os/rye
pip install -e .
```

### Connect to Your Agent

**Opencode (`.opencode/mcp.json`):**

```json
{
  "mcpServers": {
    "rye": {
      "type": "local",
      "command": ["/path/to/rye"],
      "environment": {
        "USER_SPACE": "~/.ai"
      },
      "enabled": true
    }
  }
}
```

**Cursor, Windsurf, or any MCP client:** Configure MCP server path to `rye`.

---

## The Fulcrum

> _"Give me a lever long enough and a fulcrum upon which to place it and I shall move the earth."_ — Archimedes

If AI is the lever, this is the fulcrum.

RYE doesn't just run tools—it captures the fundamental physics of AI execution as data. Once you encode workflows, tools, and knowledge as structured data, they become:

- **Portable**: Works in any MCP environment
- **Composable**: Chain directives together
- **Verifiable**: Cryptographic signatures
- **Shareable**: Registry-based distribution
- **Secure**: Capability-based permissions

This is the future of AI architecture. Once you see it, you can't unsee it.

---

## License

MIT
