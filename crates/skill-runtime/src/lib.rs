//! skill-runtime — Bridge trait and runtime dispatching.
//!
//! The Bridge trait is the core interface that any execution backend must implement:
//! - `PythonBridge`    — in-process Python (via PyO3 `Python::with_gil`)
//! - `SubprocessBridge` — out-of-process (mayapy, hython, blender --background)
//! - `HttpBridge`      — remote HTTP endpoint (future)
//!
//! skill-native-sdk is to WSGI what dcc-mcp-core is to Django:
//! `skill-runtime` defines the interface; specific DCC adapters implement it.

pub mod bridge;
pub mod subprocess;

#[cfg(feature = "python-bindings")]
pub mod python;

pub use bridge::{Bridge, BridgeError, ExecutionRequest, ExecutionResponse};
pub use subprocess::SubprocessBridge;

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn execution_request_roundtrip() {
        let req = ExecutionRequest {
            skill_name: "maya-animation".to_string(),
            tool_name: "get_keyframes".to_string(),
            params: serde_json::json!({"object": "pCube1"}),
            confirmed: false,
        };
        let json = serde_json::to_string(&req).unwrap();
        let back: ExecutionRequest = serde_json::from_str(&json).unwrap();
        assert_eq!(req.skill_name, back.skill_name);
        assert_eq!(req.tool_name, back.tool_name);
    }
}
