# skill-native-sdk

> **SKILL.md → anywhere**
>
> Write once in SKILL.md, deploy as MCP / OpenAI / LangChain / REST

[![PyPI version](https://badge.fury.io/py/skill-native-sdk.svg)](https://badge.fury.io/py/skill-native-sdk)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What is skill-native-sdk?

skill-native-sdk is the **next-generation AI tool integration architecture** that upgrades tool metadata from code comments to first-class structured declarations, enabling AI to understand the **semantics, safety boundaries, and execution relationships** of tools — not just their call signatures.

```
SKILL.md (Skill Gene)
  = Semantics + Safety Declarations + Execution Hints + Capability Graph
        ↓
  Runtime reads → Auto-builds typed execution layer
        ↓
  LLM gets not a "tool list" but a "capability map"
```

## Core Innovation

| Dimension | Traditional MCP | skill-native-sdk |
|-----------|----------------|-----------------|
| Deployment | Independent process | One SKILL.md file |
| Protocol | JSON-RPC | None — LLM reads directly |
| Tool description | `@tool` decorator in code | Natural language Markdown |
| Parallel scheduling | None | `read_only` tools auto-parallel |
| Result caching | None | `idempotent` tools auto-cached |
| Next actions | None | `on_success` auto-injected |
| Safety semantics | None | `destructive` → confirmation required |

## Quick Start

```python
from skill_native_sdk import SkillRegistry
from skill_native_sdk.adapters.mcp import MCPServer

# 3 lines to a full MCP Server
registry = SkillRegistry.from_path("./my-skills")
server = MCPServer(registry)
server.serve()
```

## Architecture

```
skill-native-sdk          ← Universal layer (this project)
│   SkillSpec v2 (Python + Rust)
│   ToolResult protocol
│   DAG Scheduler
│   Bridge trait
│   MCP Adapter
│   OpenAI Adapter
│   LangChain Adapter
│
├── dcc-mcp-core          ← DCC-specific (independent)
│   ├── dcc-mcp-maya
│   ├── dcc-mcp-houdini
│   └── dcc-mcp-blender
│
├── skill-finance         ← Finance industry skills
├── skill-medical         ← Medical industry skills
└── skill-xxx             ← Any industry plugin
```

> Analogy: **skill-native-sdk is WSGI, dcc-mcp-core is Django** — interface definition and best implementation evolve independently.

## CLI

```bash
# Discover capabilities
skill list
skill list --domain maya
skill describe maya-animation
skill graph maya-animation

# Execute
skill run maya-animation set_keyframe --object pCube1 --time 24

# Chain execution (killer feature)
skill chain maya-animation \
    --entry set_keyframe \
    --params '{"object": "pCube1", "time": 24}' \
    --follow-success

# Output formats
skill run ... --output toon    # minimal tokens
skill run ... --output mcp     # standard MCP
skill run ... --output json    # full JSON
```

## Documentation

- [SKILL_SPEC_V2.md](docs/SKILL_SPEC_V2.md) — Full SKILL.md v2 specification
- [Examples](skills/examples/) — Cross-industry example skills

## License

MIT License — see [LICENSE](LICENSE)
