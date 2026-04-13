//! SubprocessBridge — executes skill scripts as external processes.
//!
//! Supports any interpreter: `python`, `mayapy`, `hython`, `blender`.
//! The script is called with the params JSON as a command-line argument.

use std::path::Path;
use std::process::Command;
use std::time::Instant;

use skill_core::ToolResult;

use crate::bridge::{Bridge, BridgeError, ExecutionRequest, ExecutionResponse};
use skill_schema::SkillSpec;

pub struct SubprocessBridge {
    /// Default interpreter if `spec.runtime.interpreter` is not set.
    pub default_interpreter: String,
    /// Timeout in seconds.
    pub timeout_secs: u64,
}

impl Default for SubprocessBridge {
    fn default() -> Self {
        Self {
            default_interpreter: "python".to_string(),
            timeout_secs: 60,
        }
    }
}

impl SubprocessBridge {
    pub fn new(interpreter: impl Into<String>, timeout_secs: u64) -> Self {
        Self {
            default_interpreter: interpreter.into(),
            timeout_secs,
        }
    }
}

impl Bridge for SubprocessBridge {
    fn name(&self) -> &'static str {
        "subprocess"
    }

    fn execute(
        &self,
        spec: &SkillSpec,
        req: &ExecutionRequest,
    ) -> Result<ExecutionResponse, BridgeError> {
        // Resolve the script file
        let tool = spec
            .get_tool(&req.tool_name)
            .ok_or_else(|| BridgeError::EntryNotFound {
                entry: req.tool_name.clone(),
                script: spec.source_dir.clone(),
            })?;

        let source_file = tool.source_file.as_deref().ok_or_else(|| {
            BridgeError::ScriptNotFound(format!("tool '{}' has no source_file", req.tool_name))
        })?;

        let script_path = Path::new(&spec.source_dir).join(source_file);
        if !script_path.exists() {
            return Err(BridgeError::ScriptNotFound(
                script_path.display().to_string(),
            ));
        }

        let interpreter = spec
            .runtime
            .interpreter
            .as_deref()
            .unwrap_or(&self.default_interpreter);

        let params_json = serde_json::to_string(&req.params).unwrap_or_else(|_| "{}".to_string());

        let start = Instant::now();

        let output = Command::new(interpreter)
            .arg(&script_path)
            .arg(&params_json)
            .output()
            .map_err(|e| BridgeError::ExecutionFailed(e.to_string()))?;

        let duration_ms = start.elapsed().as_millis() as u64;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            return Ok(ExecutionResponse {
                result: ToolResult::fail(stderr),
                duration_ms,
                bridge_name: self.name(),
            });
        }

        let stdout = String::from_utf8_lossy(&output.stdout);
        let result: ToolResult = serde_json::from_str(stdout.trim())
            .map_err(|e| BridgeError::OutputParse(format!("{e}: output was: {stdout}")))?;

        Ok(ExecutionResponse {
            result,
            duration_ms,
            bridge_name: self.name(),
        })
    }

    fn supports(&self, runtime_type: &str) -> bool {
        // Accept both "subprocess" (explicit) and "python" (common shorthand)
        matches!(runtime_type, "subprocess" | "python")
    }
}
