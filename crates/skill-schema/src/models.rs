//! SKILL.md v2 data models — serde types for deserialisation + optional PyO3 classes.

use std::path::PathBuf;

use indexmap::IndexMap;
use serde::{Deserialize, Serialize};

use crate::scope::SkillScope;

// ── FieldSchema ──────────────────────────────────────────────────────────────

/// Describes a single input parameter of a tool.
#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq)]
#[serde(default)]
pub struct FieldSchema {
    #[serde(rename = "type", default = "default_field_type")]
    pub field_type: String,
    pub description: String,
    pub required: bool,
    pub default: Option<serde_json::Value>,
    pub enum_values: Option<Vec<serde_json::Value>>,
}

fn default_field_type() -> String {
    "string".to_string()
}

// ── ChainHint ────────────────────────────────────────────────────────────────

/// Execution chain hints injected into LLM context after tool completion.
#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq)]
#[serde(default)]
pub struct ChainHint {
    pub suggest: Vec<String>,
}

// ── RuntimeConfig ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(default)]
pub struct RuntimeConfig {
    #[serde(rename = "type")]
    pub runtime_type: String,
    pub entry: String,
    pub interpreter: Option<String>,
}

impl Default for RuntimeConfig {
    fn default() -> Self {
        Self {
            runtime_type: "python".to_string(),
            entry: "skill_entry".to_string(),
            interpreter: None,
        }
    }
}

// ── Permissions ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq)]
#[serde(default)]
pub struct Permissions {
    pub network: bool,
    #[serde(default = "default_filesystem")]
    pub filesystem: String,
    pub external_api: bool,
}

fn default_filesystem() -> String {
    "none".to_string()
}

// ── ToolMeta ──────────────────────────────────────────────────────────────────

/// Metadata for a single tool declared in SKILL.md.
#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq)]
#[serde(default)]
pub struct ToolMeta {
    pub name: String,
    pub description: String,
    pub source_file: Option<String>,

    // Safety semantics
    pub read_only: bool,
    pub destructive: bool,
    pub idempotent: bool,

    // Cost hints
    #[serde(default = "default_cost")]
    pub cost: String,
    #[serde(default = "default_latency")]
    pub latency: String,

    // I/O schemas
    pub input: IndexMap<String, FieldSchema>,
    pub output: IndexMap<String, String>,

    // Chain hints
    pub on_success: ChainHint,
    pub on_error: ChainHint,
}

fn default_cost() -> String {
    "low".to_string()
}
fn default_latency() -> String {
    "fast".to_string()
}

// ── SkillMetadata ─────────────────────────────────────────────────────────────

/// Lightweight metadata loaded during discovery (no full YAML parse).
///
/// Only `name`, `description`, and a few index fields are populated.
/// Call [`SkillMetadata::load`] to obtain the full [`SkillSpec`].
#[derive(Debug, Clone)]
pub struct SkillMetadata {
    pub name: String,
    pub description: String,
    pub domain: String,
    pub version: String,
    pub tags: Vec<String>,
    /// Priority scope this skill was discovered under.
    pub scope: SkillScope,
    /// Absolute path to the `SKILL.md` file.
    pub path_to_skill_md: PathBuf,
    /// Parent directory of `path_to_skill_md`.
    pub source_dir: String,
}

impl SkillMetadata {
    /// Lazily load the full [`SkillSpec`] from disk.
    pub fn load(&self) -> Result<SkillSpec, crate::ParseError> {
        crate::parser::parse_skill_md_with_scope(&self.path_to_skill_md, self.scope)
    }
}

// ── ScanError ─────────────────────────────────────────────────────────────────

/// A skill file that failed to parse during discovery.
#[derive(Debug, Clone)]
pub struct ScanError {
    /// Path to the offending `SKILL.md`.
    pub path: PathBuf,
    /// Human-readable error description.
    pub message: String,
}

// ── ScanOutcome ───────────────────────────────────────────────────────────────

/// Result of a progressive skill discovery scan.
///
/// `metadata` contains lightweight records for every skill found.
/// Use [`SkillMetadata::load`] to obtain a full [`SkillSpec`] on demand.
#[derive(Debug, Default, Clone)]
pub struct ScanOutcome {
    /// Lightweight records — sorted by scope priority, then name.
    pub metadata: Vec<SkillMetadata>,
    /// Skills that could not be parsed.
    pub errors: Vec<ScanError>,
}

impl ScanOutcome {
    /// Total number of successfully discovered skills.
    pub fn len(&self) -> usize {
        self.metadata.len()
    }

    /// Whether no skills were found.
    pub fn is_empty(&self) -> bool {
        self.metadata.is_empty()
    }

    /// Find metadata by skill name.
    pub fn find(&self, name: &str) -> Option<&SkillMetadata> {
        self.metadata.iter().find(|m| m.name == name)
    }
}

// ── SkillSpec ─────────────────────────────────────────────────────────────────

/// Top-level SKILL.md v2 specification — parsed from YAML front-matter.
#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq)]
#[serde(default)]
pub struct SkillSpec {
    // Identity
    pub name: String,
    pub domain: String,
    pub version: String,
    pub description: String,
    pub tags: Vec<String>,

    // Tools
    pub tools: Vec<ToolMeta>,

    // Runtime
    pub runtime: RuntimeConfig,

    // Permissions
    pub permissions: Permissions,

    // Set at load time (not in YAML) ─────────────────────────────────────────
    /// Parent directory of the SKILL.md file.
    #[serde(skip)]
    pub source_dir: String,
    /// Priority scope this skill was discovered under.
    #[serde(skip)]
    pub scope: SkillScope,
    /// Absolute path to the SKILL.md file (empty when parsed from string).
    #[serde(skip)]
    pub path_to_skill_md: PathBuf,
}

impl SkillSpec {
    /// Find a tool by name.
    pub fn get_tool(&self, name: &str) -> Option<&ToolMeta> {
        self.tools.iter().find(|t| t.name == name)
    }

    /// Tools that are safe to run without confirmation.
    pub fn readonly_tools(&self) -> Vec<&ToolMeta> {
        self.tools.iter().filter(|t| t.read_only).collect()
    }

    /// Tools that are safe to parallelize with any other read-only tool.
    pub fn parallelizable_tools(&self) -> Vec<&ToolMeta> {
        self.tools
            .iter()
            .filter(|t| t.read_only && t.idempotent)
            .collect()
    }

    /// Entry-point tools: those NOT mentioned in any on_success/on_error of other tools.
    pub fn entry_points(&self) -> Vec<&str> {
        let mentioned: std::collections::HashSet<&str> = self
            .tools
            .iter()
            .flat_map(|t| t.on_success.suggest.iter().chain(t.on_error.suggest.iter()))
            .map(|s| s.as_str())
            .collect();
        self.tools
            .iter()
            .filter(|t| !mentioned.contains(t.name.as_str()))
            .map(|t| t.name.as_str())
            .collect()
    }
}
