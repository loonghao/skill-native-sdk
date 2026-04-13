//! skill-schema — SKILL.md v2 schema types and YAML parser.
//!
//! This crate provides:
//! - [`SkillSpec`] — the top-level parsed SKILL.md v2 structure
//! - [`ToolMeta`] — a single tool declaration
//! - [`parse_skill_md`] — parse a SKILL.md file or directory
//! - [`scan_and_load`] — recursively discover all skills under a root path

pub mod models;
pub mod parser;

#[cfg(feature = "python-bindings")]
pub mod python;

pub use models::*;
pub use parser::{parse_skill_md, parse_skill_md_str, scan_and_load};

// ── Error types ───────────────────────────────────────────────────────────────

use std::path::PathBuf;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ParseError {
    #[error("path not found: {0}")]
    NotFound(PathBuf),

    #[error("YAML parse error: {0}")]
    Yaml(String),

    #[error("IO error reading {0}: {1}")]
    Io(PathBuf, #[source] std::io::Error),
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE: &str = r#"---
name: test-skill
domain: maya
version: "1.0.0"
description: "A test skill"
tags: [test, maya]

tools:
  - name: set_keyframe
    description: "Set a keyframe"
    read_only: false
    destructive: false
    idempotent: false
    cost: low
    latency: fast
    input:
      object:
        type: string
        required: true
        description: "Maya object name"
      time:
        type: number
        required: true
    on_success:
      suggest: [get_keyframes]

  - name: get_keyframes
    description: "Query keyframes"
    read_only: true
    idempotent: true

runtime:
  type: python
  entry: skill_entry

permissions:
  network: false
  filesystem: none
---
"#;

    #[test]
    fn test_parse_frontmatter() {
        let spec = parse_skill_md_str(SAMPLE, "/tmp/test".to_string()).unwrap();
        assert_eq!(spec.name, "test-skill");
        assert_eq!(spec.domain, "maya");
        assert_eq!(spec.tools.len(), 2);
    }

    #[test]
    fn test_tool_safety_fields() {
        let spec = parse_skill_md_str(SAMPLE, "/tmp".to_string()).unwrap();
        let tool = spec.get_tool("set_keyframe").unwrap();
        assert!(!tool.read_only);
        assert!(!tool.destructive);
        assert_eq!(tool.on_success.suggest, vec!["get_keyframes"]);
    }

    #[test]
    fn test_entry_points() {
        let spec = parse_skill_md_str(SAMPLE, "/tmp".to_string()).unwrap();
        let entries = spec.entry_points();
        assert!(entries.contains(&"set_keyframe"));
        assert!(!entries.contains(&"get_keyframes"));
    }

    #[test]
    fn test_readonly_tools() {
        let spec = parse_skill_md_str(SAMPLE, "/tmp".to_string()).unwrap();
        let ro = spec.readonly_tools();
        assert_eq!(ro.len(), 1);
        assert_eq!(ro[0].name, "get_keyframes");
    }

    #[test]
    fn test_input_field_parsing() {
        let spec = parse_skill_md_str(SAMPLE, "/tmp".to_string()).unwrap();
        let tool = spec.get_tool("set_keyframe").unwrap();
        let obj = tool.input.get("object").unwrap();
        assert_eq!(obj.field_type, "string");
        assert!(obj.required);
    }
}
