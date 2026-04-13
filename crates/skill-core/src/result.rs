//! ToolResult — structured output from any skill tool execution.

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Structured, protocol-agnostic result from a skill tool execution.
///
/// Three serialisation formats are supported:
/// - [`ToolResult::to_json`]  — full JSON (standard)
/// - [`ToolResult::to_toon`]  — minimal token format for LLM consumption
/// - [`ToolResult::to_mcp`]   — MCP `tool_result` wire format
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct ToolResult {
    pub success: bool,
    pub message: String,
    pub data: Option<Value>,
    pub next_actions: Vec<String>,
    pub error: Option<String>,
    pub metadata: std::collections::HashMap<String, Value>,
}

impl ToolResult {
    /// Successful result.
    pub fn ok(message: impl Into<String>) -> Self {
        Self {
            success: true,
            message: message.into(),
            ..Default::default()
        }
    }

    /// Successful result with data payload.
    pub fn ok_with_data(message: impl Into<String>, data: Value) -> Self {
        Self {
            success: true,
            message: message.into(),
            data: Some(data),
            ..Default::default()
        }
    }

    /// Failed result.
    pub fn fail(error: impl Into<String>) -> Self {
        let error = error.into();
        Self {
            success: false,
            message: error.clone(),
            error: Some(error),
            ..Default::default()
        }
    }

    /// Inject on_success chain hints.
    pub fn with_next(mut self, actions: Vec<String>) -> Self {
        self.next_actions = actions;
        self
    }

    // ── Serialisation formats ─────────────────────────────────────────────

    /// Full JSON serialisation (the default format).
    pub fn to_json(&self) -> String {
        serde_json::to_string(self).unwrap_or_else(|e| format!(r#"{{"error":"{}"}}"#, e))
    }

    /// Minimal token format — reduces LLM context consumption by ~3-5×.
    ///
    /// ```json
    /// {"ok": true, "msg": "done", "next": ["next_tool"]}
    /// ```
    pub fn to_toon(&self) -> Value {
        let mut m = serde_json::Map::new();
        m.insert("ok".to_string(), Value::Bool(self.success));
        m.insert("msg".to_string(), Value::String(self.message.clone()));
        m.insert(
            "next".to_string(),
            Value::Array(
                self.next_actions
                    .iter()
                    .map(|s| Value::String(s.clone()))
                    .collect(),
            ),
        );
        if let Some(err) = &self.error {
            m.insert("err".to_string(), Value::String(err.clone()));
        }
        if let Some(data) = &self.data {
            m.insert("data".to_string(), data.clone());
        }
        Value::Object(m)
    }

    /// MCP `tool_result` wire format.
    pub fn to_mcp(&self) -> Value {
        serde_json::json!({
            "type": "tool_result",
            "content": [{"type": "text", "text": self.message}],
            "isError": !self.success,
        })
    }
}

impl std::fmt::Display for ToolResult {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "ToolResult(success={}, msg={:?})",
            self.success, self.message
        )
    }
}
