# Help Tool (`mcp__rye__help`)

## Purpose

Get help and usage guidance for RYE MCP tools and concepts.

## Request Schema

```json
{
  "topic": "string"  // Optional, defaults to "overview"
}
```

## Available Topics

| Topic | Description |
|-------|-------------|
| `overview` | General RYE MCP overview |
| `search` | Help for search tool |
| `load` | Help for load tool |
| `execute` | Help for execute tool |
| `sign` | Help for sign tool |
| `directives` | About directive items |
| `tools` | About tool items |
| `knowledge` | About knowledge items |

## Response Schema

```json
{
  "status": "help",
  "topic": "string",
  "content": "string"
}
```

## Examples

### Get Overview

**Request:**
```json
{
  "topic": "overview"
}
```

**Response:**
```json
{
  "status": "help",
  "topic": "overview",
  "content": "RYE MCP - Unified MCP for directives, tools, and knowledge\n\nThis MCP provides 5 tools:\n- search: Find items across project and user space\n- load: Load items for inspection or copy between locations\n- execute: Run/execute items\n- sign: Validate and sign items\n- help: Get help and guidance\n\nTypes supported:\n- directive: Workflow definitions\n- tool: Executable tools\n- knowledge: Knowledge base entries"
}
```

### Get Search Help

**Request:**
```json
{
  "topic": "search"
}
```

**Response:**
```json
{
  "status": "help",
  "topic": "search",
  "content": "search - Find items across project or user space\n\nParameters:\n- item_type: \"directive\" | \"tool\" | \"knowledge\" (required)\n- query: Search query as natural language or keywords (required)\n- source: \"project\" | \"user\" (default: \"project\")\n- limit: Max results (default: 10)\n\nExample:\nsearch(item_type=\"directive\", query=\"lead generation\", source=\"project\")"
}
```

### Get Execute Help

**Request:**
```json
{
  "topic": "execute"
}
```

## Default Behavior

When no topic is provided, returns the overview:

**Request:**
```json
{}
```

**Response:**
```json
{
  "status": "help",
  "topic": "overview",
  "content": "..."
}
```

## Related Documentation

- [[../mcp-server]] - MCP server architecture
- [[search]] - Search for items
- [[load]] - Load item content
- [[execute]] - Execute items
- [[sign]] - Sign items
