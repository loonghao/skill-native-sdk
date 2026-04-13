# SKILL.md v2 Specification

> Version: 2.0.0 | Status: Draft | Updated: 2026-04-13

## Overview

SKILL.md is the "gene" of a skill — a single structured file that defines:

- **Semantics** — what the skill does, in which domain
- **Safety declarations** — read_only, destructive, idempotent
- **Execution hints** — cost, latency, on_success, on_error chains
- **Capability graph** — how tools relate to each other
- **Permissions** — network, filesystem, external API access

## Format

SKILL.md uses YAML front-matter (between `---` delimiters). The rest of the file is free-form Markdown for human documentation.

## Full Schema

```yaml
# === Identity Layer ===
name: my-skill               # Required. Unique identifier.
domain: generic              # Industry tag: maya / finance / medical / gamedev / generic
version: "1.0.0"             # Semantic version string
description: "..."           # One-line description
tags: [tag1, tag2]           # Searchable tags

# === Tools Declaration Layer ===
tools:
  - name: tool_name          # Required. Snake_case tool identifier.
    description: "..."       # Human + LLM description. Be specific!
    source_file: scripts/tool.py  # Path relative to SKILL.md directory

    # Safety Semantics (all AI runtimes should respect these)
    read_only: true          # Does not modify state
    destructive: false       # Cannot be undone (e.g. delete, transfer)
    idempotent: false        # Same input always produces same result

    # Execution Cost Hints
    cost: low                # low / medium / high / external
    latency: fast            # fast(<1s) / normal(<5s) / slow(>5s)

    # Input Schema
    input:
      param_name:
        type: string         # string / number / boolean / array / object
        required: true
        description: "..."
        default: null
        enum: null           # Optional: list of allowed values

    # Output Schema (informational)
    output:
      field_name: type       # Simple key: type mapping

    # Chain Hints — guide LLM to next steps
    on_success:
      suggest: [next_tool_1, next_tool_2]
    on_error:
      suggest: [fallback_tool]

    # Agent Behavior Hints
    agent_hint:
      prefer: cli            # Prefer CLI execution over code generation
      cli_entry: "skill run"

# === Runtime Bridge Layer ===
runtime:
  type: python               # python / rust / wasm / http / subprocess
  entry: skill_entry         # Function name to call (default: skill_entry)
  interpreter: null          # For subprocess: mayapy / hython / blender

# === Permission Declarations ===
permissions:
  network: false
  filesystem: none           # none / read / write / full
  external_api: false
```

## Safety Semantics

| Field | Meaning | Runtime Behavior |
|-------|---------|-----------------|
| `read_only: true` | Does not modify state | Safe to parallelize; safe to retry |
| `destructive: true` | Cannot be undone | Adapter MUST prompt for confirmation |
| `idempotent: true` | Same inputs → same output | Adapter MAY cache results |

## Capability Graph

When loaded by skill-native-sdk, each skill automatically generates a CapabilityGraph:

```json
{
  "skill": "invoice-parser",
  "domain": "finance",
  "entry_points": ["parse_invoice"],
  "graph": {
    "parse_invoice": {
      "on_success": ["validate_invoice", "post_to_accounting"],
      "on_error": ["ocr_fallback"],
      "safe_to_parallelize_with": []
    }
  },
  "terminal_nodes": ["post_to_accounting", "manual_review_flag"]
}
```

This transforms the LLM from a "tool selector" into a "graph traverser" — more reliable, fewer tokens, more predictable.

## Token-Efficient Output (toon format)

Instead of verbose JSON results, use `--output toon`:

```json
{"ok": true, "msg": "Set keyframe on pCube1.translateX at frame 24", "next": ["get_keyframes"]}
```

vs standard JSON (~3-5x more tokens):

```json
{"success": true, "message": "Set keyframe...", "data": null, "next_actions": ["get_keyframes"], "error": null, "metadata": {}}
```

## Industry Examples

| Field | DCC/CG (Maya) | Finance | Medical | Game Dev |
|-------|--------------|---------|---------|---------|
| `domain` | `maya` | `finance` | `medical` | `gamedev` |
| `runtime.type` | `python` | `python` | `python` | `subprocess` |
| `destructive` example | delete mesh | wire transfer | write diagnosis | delete save |
| `filesystem` | `none` | `none` | `read` | `write` |

## Bridge Architecture

```
skill-native-sdk
      ↓
 Bridge Router
      │
      ├── MayaBridge (needs Maya online)
      │     → in-process cmds calls
      │
      ├── SubprocessBridge (no GUI needed)
      │     → mayapy / hython / blender --background
      │
      ├── FarmBridge (no DCC needed)
      │     → submit to Deadline / Tractor
      │
      └── AssetBridge (no DCC needed)
            → query Shotgrid / ftrack
```

## Agent Integration

To make LLM agents always prefer CLI tools over generating code, use the **MCP Tool Wrapper** pattern:

```json
{
  "name": "skill_run",
  "description": "ALWAYS use this before writing any code. Executes any skill tool with safety checks, caching, and chain support.",
  "inputSchema": {
    "skill_name": {"type": "string"},
    "tool_name": {"type": "string"},
    "params": {"type": "object"},
    "output_format": {"enum": ["toon", "json", "mcp"], "default": "toon"}
  }
}
```

The `"ALWAYS use this before writing any code"` instruction is key — LLMs respond well to strong description-level directives.
