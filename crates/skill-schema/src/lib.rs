//! skill-schema — SKILL.md v2 schema types and YAML parser.
//!
//! ## Quick start
//!
//! ```rust,no_run
//! use skill_schema::manager::SkillsManager;
//!
//! // Progressive discovery (recommended)
//! let mgr = SkillsManager::new();
//! let outcome = mgr.scan_for_cwd(std::path::Path::new("."), false);
//! for meta in &outcome.metadata {
//!     println!("[{}] {} — {}", meta.scope, meta.name, meta.description);
//!     let spec = meta.load().unwrap();   // lazy full parse
//!     println!("  {} tools", spec.tools.len());
//! }
//!
//! // One-shot backward-compatible scan
//! use skill_schema::scan_and_load;
//! let specs = scan_and_load(std::path::Path::new("./skills"));
//! ```

pub mod manager;
pub mod models;
pub mod parser;
pub mod scope;

#[cfg(feature = "python-bindings")]
pub mod python;

// Flat re-exports — keeps existing call sites unchanged
pub use manager::{find_git_root, scan_explicit_roots, skill_roots_for_cwd, user_skills_dir,
                  SkillsManager};
pub use models::*;
pub use parser::{
    load_skills_from_roots, parse_frontmatter_only, parse_skill_md, parse_skill_md_str,
    parse_skill_md_with_scope, scan_and_load,
};
pub use scope::{SkillRoot, SkillScope};

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
