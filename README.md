# skill-native-sdk

<p align="center">
  <b>SKILL.md → MCP / OpenAI / LangChain / REST</b><br/>
  Write once. Deploy anywhere. Zero Python dependencies.
</p>

<p align="center">
  <a href="https://pypi.org/project/skill-native-sdk/"><img src="https://badge.fury.io/py/skill-native-sdk.svg" alt="PyPI"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.7%2B-blue.svg" alt="Python 3.7+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT"></a>
  <img src="https://img.shields.io/badge/core-Rust-orange.svg" alt="Rust core">
</p>

---

## What is skill-native-sdk?

`skill-native-sdk` is an **AI tool integration framework** where every capability is declared in a single `SKILL.md` file and automatically exposed as MCP, OpenAI function, or LangChain tool — without changing any Python code.

```
SKILL.md  (the "skill gene")
  name / domain / version / description
  tools:  [name, safety semantics, I/O schema, chain hints]
  runtime: { type: python, entry: skill_entry }
  permissions: { network: false, filesystem: none }
       ↓
  skn list / describe / run / chain
       ↓
  MCP Server  ·  OpenAI functions  ·  LangChain tools  ·  REST
```

### Why not just use plain MCP?

| Dimension | Plain MCP tool | skill-native-sdk |
|-----------|---------------|------------------|
| Metadata | `@tool` decorator | First-class `SKILL.md` |
| Parallel scheduling | ✗ | `read_only` tools auto-parallel |
| Result caching | ✗ | `idempotent` tools auto-cached |
| Next-action hints | ✗ | `on_success` injected into LLM context |
| Safety gate | ✗ | `destructive: true` → confirmation required |
| Discovery | Manual registry | Layered BFS (project → user → system) |
| Python overhead | Required | Zero runtime deps (Rust core + stdlib shim) |

---

## CLI — `skn`

The CLI is named **`skn`** (sk·ill-n·ative) — short, unique, and conflict-free.

```bash
# Progressive discovery — lists skills without parsing full YAML
skn list
skn list --domain maya

# Lazy-load full spec only for the target skill
skn describe maya-animation
skn graph maya-animation

# Execute
skn run maya-animation set_keyframe --params '{"object":"pCube1","time":24}'

# Chain: follow on_success hints automatically
skn chain maya-animation \
    --entry set_keyframe \
    --params '{"object":"pCube1","time":24}' \
    --follow-success

# Output formats
skn run ... --output toon   # minimal tokens (~3-5× smaller)
skn run ... --output mcp    # MCP tool_result wire format
skn run ... --output json   # full JSON (default)
```

### How `skn list` works (progressive loading)

```
skn list
  │
  ├─ SkillsManager.scan_for_cwd(cwd)
  │    ├─ Repo:   .codex/skills/  skills/  (walks up to git root)
  │    └─ User:   ~/.skill-native/skills/
  │
  ├─ BFS each root  (MAX_DEPTH=6, MAX_DIRS=2000, hidden dirs skipped)
  │    └─ parse_frontmatter_only() ← reads ONLY name/description/domain
  │         (no full YAML parse — instant even with 1000 skills)
  │
  └─ Dedup by canonical path, sort by scope priority (Repo > User)
       then display — zero full YAML loaded
```

`skn describe` / `skn run` call `meta.load()` **only** for the chosen skill.


---

## Installation

```bash
pip install skill-native-sdk        # includes skn CLI + Rust core wheel
```

After install, the `skn` command is available globally:

```bash
skn --version
skn list
```

> **Python 3.7+** supported. The Rust core ships as a single ABI3 wheel for
> Python 3.8–3.13+. Python 3.7 gets a separate `cp37` wheel.

---

## Writing a SKILL.md

```yaml
---
name: maya-animation
domain: maya
version: "1.0.0"
description: "Keyframe animation tools for Autodesk Maya"
tags: [maya, animation, dcc]

tools:
  - name: set_keyframe
    description: "Set a keyframe on a Maya object"
    read_only: false
    idempotent: false
    input:
      object: { type: string, required: true }
      time:   { type: number, required: true }
    on_success:
      suggest: [get_keyframes]   # hint injected into LLM context after call

  - name: get_keyframes
    description: "Query all keyframes for an object"
    read_only: true
    idempotent: true              # safe to cache + parallelize

runtime:
  type: python
  entry: skill_entry

permissions:
  network: false
  filesystem: read
---
```

Place at `./skills/maya-animation/SKILL.md` — `skn list` finds it instantly.

---

## Python API

```python
# One-shot parse
from skill_native_sdk.parser import parse_skill_md
spec = parse_skill_md("./skills/maya-animation")
print(spec.name, len(spec.tools))

# Progressive discovery (recommended for large collections)
from skill_native_sdk._skill_native_core import SkillsManager
mgr = SkillsManager()
outcome = mgr.scan_for_cwd(".")          # reads ONLY name+desc per skill
for meta in outcome.metadata:
    print(meta.scope, meta.name)         # "repo  maya-animation"
    spec = meta.load()                   # lazy — full YAML only here

# MCP server (3 lines)
from skill_native_sdk import SkillRegistry
from skill_native_sdk.adapters.mcp import MCPServer
MCPServer(SkillRegistry.from_path("./skills")).serve()
```

---

## Architecture

```
skill-native-sdk
├── crates/
│   ├── skill-schema   ← SKILL.md v2 parser · SkillScope · SkillsManager
│   ├── skill-core     ← ToolResult · DAG scheduler · SafetyChecker · ResultCache
│   ├── skill-runtime  ← Bridge trait · SubprocessBridge
│   └── skill-cli      ← skn CLI (clap) · 5 subcommands · ANSI display
└── python/skill_native_sdk/
    ├── models.py      ← stdlib dataclasses (zero runtime deps)
    ├── parser.py      ← Rust-first, stdlib fallback
    ├── registry.py / executor.py
    ├── cli/main.py    ← thin shim → _skill_native_core.run_cli(sys.argv)
    └── adapters/mcp · openai
```

---

## Skill discovery roots

| Scope | Paths | Priority |
|-------|-------|---------|
| **Repo** | `.codex/skills/`, `skills/` — walks up to git root | Highest |
| **User** | `~/.skill-native/skills/` · `$SKILL_NATIVE_HOME/skills/` | Middle |
| **System** | *(future: embedded built-ins)* | Lowest |

Same canonical path → first root (highest scope) wins. BFS depth ≤ 6, ≤ 2000 dirs/root.

---

## Development

```bash
cargo install just
just dev        # maturin develop
just preflight  # clippy -D warnings + fmt + cargo test
just test       # pytest
just build      # ABI3 wheel (Python 3.8+)
```

---

## Related projects

| Project | Role |
|---------|------|
| [dcc-mcp-core](https://github.com/loonghao/dcc-mcp-core) | DCC adapters (Maya, Houdini, Blender) |
| [openai/codex](https://github.com/openai/codex) | Inspiration for layered skill discovery |

---

## License

MIT — see [LICENSE](LICENSE)
