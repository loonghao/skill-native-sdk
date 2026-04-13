//! SKILL.md v2 data models — serde types for deserialisation + optional PyO3 classes.

use indexmap::IndexMap;
use serde::{Deserialize, Serialize};

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

    // Set at load time (not in YAML)
    #[serde(skip)]
    pub source_dir: String,
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
        self.tools.iter().filter(|t| t.read_only && t.idempotent).collect()
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
