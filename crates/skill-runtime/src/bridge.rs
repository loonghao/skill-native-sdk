//! Bridge trait — the core interface every runtime adapter must implement.

use serde::{Deserialize, Serialize};
use skill_core::ToolResult;
use thiserror::Error;

// ── Error type ────────────────────────────────────────────────────────────────

#[derive(Debug, Error)]
pub enum BridgeError {
    #[error("script not found: {0}")]
    ScriptNotFound(String),

    #[error("entry point '{entry}' not found in {script}")]
    EntryNotFound { entry: String, script: String },

    #[error("execution failed: {0}")]
    ExecutionFailed(String),

    #[error("output parse error: {0}")]
    OutputParse(String),

    #[error("timeout after {seconds}s")]
    Timeout { seconds: u64 },

    #[error("unsupported runtime type: {0}")]
    Unsupported(String),
}

// ── Request / Response ────────────────────────────────────────────────────────

/// Input to a bridge execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionRequest {
    pub skill_name: String,
    pub tool_name: String,
    pub params: serde_json::Value,
    /// `true` if the caller has confirmed a destructive operation.
    pub confirmed: bool,
}

/// Output of a bridge execution (wraps [`ToolResult`] with bridge metadata).
#[derive(Debug, Clone)]
pub struct ExecutionResponse {
    pub result: ToolResult,
    /// Duration in milliseconds.
    pub duration_ms: u64,
    /// Which bridge was used.
    pub bridge_name: &'static str,
}

// ── Bridge trait ─────────────────────────────────────────────────────────────

/// Core interface that every runtime backend must implement.
///
/// # Implementing a new bridge
///
/// ```rust,ignore
/// use skill_runtime::bridge::{Bridge, BridgeError, ExecutionRequest, ExecutionResponse};
/// use skill_schema::SkillSpec;
///
/// pub struct MyCustomBridge;
///
/// impl Bridge for MyCustomBridge {
///     fn name(&self) -> &'static str { "my-custom" }
///
///     fn execute(
///         &self,
///         spec: &SkillSpec,
///         req: &ExecutionRequest,
///     ) -> Result<ExecutionResponse, BridgeError> {
///         // ... your implementation
///         todo!()
///     }
///
///     fn supports(&self, runtime_type: &str) -> bool {
///         runtime_type == "my-custom"
///     }
/// }
/// ```
pub trait Bridge: Send + Sync {
    /// Human-readable bridge identifier (e.g. `"python"`, `"subprocess"`, `"http"`).
    fn name(&self) -> &'static str;

    /// Execute a tool and return the result.
    fn execute(
        &self,
        spec: &skill_schema::SkillSpec,
        req: &ExecutionRequest,
    ) -> Result<ExecutionResponse, BridgeError>;

    /// Returns `true` if this bridge handles the given `runtime.type` value.
    fn supports(&self, runtime_type: &str) -> bool;
}

// ── BridgeRouter ─────────────────────────────────────────────────────────────

/// Routes execution requests to the appropriate bridge based on `runtime.type`.
pub struct BridgeRouter {
    bridges: Vec<Box<dyn Bridge>>,
}

impl BridgeRouter {
    pub fn new() -> Self {
        Self { bridges: Vec::new() }
    }

    pub fn register(mut self, bridge: Box<dyn Bridge>) -> Self {
        self.bridges.push(bridge);
        self
    }

    pub fn execute(
        &self,
        spec: &skill_schema::SkillSpec,
        req: &ExecutionRequest,
    ) -> Result<ExecutionResponse, BridgeError> {
        let rt = &spec.runtime.runtime_type;
        for bridge in &self.bridges {
            if bridge.supports(rt) {
                return bridge.execute(spec, req);
            }
        }
        Err(BridgeError::Unsupported(rt.clone()))
    }
}

impl Default for BridgeRouter {
    fn default() -> Self {
        Self::new()
    }
}
