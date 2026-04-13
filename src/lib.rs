//! skill-native-sdk: Python bindings entry point.
//!
//! This root crate serves as the `skill_native_sdk._skill_native_core` Python
//! extension module.  All logic lives in workspace sub-crates; this crate only
//! re-exports and registers.

// Re-export sub-crates for Rust consumers
pub use skill_cli as cli;
pub use skill_core as core;
pub use skill_runtime as runtime;
pub use skill_schema as schema;

#[cfg(feature = "python-bindings")]
use pyo3::prelude::*;

/// Python module: `skill_native_sdk._skill_native_core`
///
/// After `maturin develop`, Python code can do:
/// ```python
/// from skill_native_sdk._skill_native_core import (
///     RustSkillSpec, RustToolResult, SafetyChecker,
///     parse_skill_md, scan_and_load, plan_execution,
/// )
/// ```
#[cfg(feature = "python-bindings")]
#[pymodule]
fn _skill_native_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // ── skill-schema: YAML parser + schema types ──────────────────────────
    skill_schema::python::register(m)?;

    // ── skill-core: ToolResult, SafetyChecker, DAG scheduler ─────────────
    skill_core::python::register(m)?;

    // ── skill-runtime: bridge constants ───────────────────────────────────
    skill_runtime::python::register(m)?;

    // ── skill-cli: run_cli() ──────────────────────────────────────────────
    skill_cli::python::register(m)?;

    // ── Metadata ──────────────────────────────────────────────────────────
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("__author__", env!("CARGO_PKG_AUTHORS"))?;

    Ok(())
}

#[cfg(test)]
mod tests {
    #[test]
    fn workspace_crates_accessible() {
        // Verify all crates compile and are accessible
        let result = skill_core::ToolResult::ok("test");
        assert!(result.success);

        let spec = skill_schema::parse_skill_md_str(
            "---\nname: test\ntools: []\n---\n",
            "/tmp".to_string(),
        )
        .unwrap();
        assert_eq!(spec.name, "test");

        let cache = skill_core::ResultCache::new(10);
        assert!(cache.is_empty());
    }
}
