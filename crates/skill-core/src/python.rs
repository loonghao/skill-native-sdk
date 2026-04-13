//! PyO3 bindings for skill-core types.

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::{
    cache::{CacheKey, ResultCache},
    dag::DagScheduler,
    result::ToolResult,
    safety::{SafetyChecker, SafetyDecision, SafetyPolicy},
};
use skill_schema::SkillSpec;

// ── PyToolResult ──────────────────────────────────────────────────────────────

#[pyclass(name = "RustToolResult")]
#[derive(Clone)]
pub struct PyToolResult(pub ToolResult);

#[pymethods]
impl PyToolResult {
    #[new]
    #[pyo3(signature = (success=true, message="", error=None))]
    fn new(success: bool, message: &str, error: Option<String>) -> Self {
        if success {
            PyToolResult(ToolResult::ok(message))
        } else {
            PyToolResult(ToolResult::fail(error.unwrap_or_else(|| message.to_string())))
        }
    }

    #[staticmethod]
    fn ok(message: &str) -> Self {
        PyToolResult(ToolResult::ok(message))
    }

    #[staticmethod]
    fn fail(error: &str) -> Self {
        PyToolResult(ToolResult::fail(error))
    }

    #[getter] fn success(&self) -> bool { self.0.success }
    #[getter] fn message(&self) -> &str { &self.0.message }
    #[getter] fn error(&self) -> Option<&str> { self.0.error.as_deref() }
    #[getter] fn next_actions(&self) -> Vec<String> { self.0.next_actions.clone() }

    fn to_json(&self) -> String { self.0.to_json() }

    fn to_toon<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let json_str = serde_json::to_string(&self.0.to_toon()).unwrap_or_default();
        let json_mod = py.import("json")?;
        json_mod.call_method1("loads", (json_str,))
    }

    fn to_mcp<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let json_str = serde_json::to_string(&self.0.to_mcp()).unwrap_or_default();
        let json_mod = py.import("json")?;
        json_mod.call_method1("loads", (json_str,))
    }

    fn to_dict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let json_str = self.0.to_json();
        let json_mod = py.import("json")?;
        json_mod.call_method1("loads", (json_str,))
    }

    fn __repr__(&self) -> String {
        format!("RustToolResult(success={}, msg={:?})", self.0.success, self.0.message)
    }
}

// ── PySafetyChecker ───────────────────────────────────────────────────────────

#[pyclass(name = "SafetyChecker")]
pub struct PySafetyChecker(SafetyChecker);

#[pymethods]
impl PySafetyChecker {
    #[new]
    #[pyo3(signature = (block_destructive=false, block_external_cost=false))]
    fn new(block_destructive: bool, block_external_cost: bool) -> Self {
        PySafetyChecker(SafetyChecker::new(SafetyPolicy { block_destructive, block_external_cost }))
    }

    /// Check a tool. Returns `("allow", "")`, `("confirm", reason)`, or `("block", reason)`.
    fn check(&self, tool_name: &str, destructive: bool, cost: &str, confirmed: bool) -> (String, String) {
        let tool = skill_schema::ToolMeta {
            name: tool_name.to_string(),
            destructive,
            cost: cost.to_string(),
            ..Default::default()
        };
        match self.0.check(&tool, confirmed) {
            SafetyDecision::Allow => ("allow".to_string(), String::new()),
            SafetyDecision::RequiresConfirmation(r) => ("confirm".to_string(), r),
            SafetyDecision::Blocked(r) => ("block".to_string(), r),
        }
    }
}

// ── PyDagScheduler ─────────────────────────────────────────────────────────────

#[pyfunction]
pub fn plan_execution(skill_json: &str, tool_names: Vec<String>) -> PyResult<Vec<Vec<String>>> {
    let spec: SkillSpec = serde_json::from_str(skill_json).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("invalid skill JSON: {e}"))
    })?;
    let refs: Vec<&str> = tool_names.iter().map(|s| s.as_str()).collect();
    let plan = DagScheduler::plan(&spec, &refs);
    Ok(plan.stages)
}

// ── Registration ──────────────────────────────────────────────────────────────

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyToolResult>()?;
    m.add_class::<PySafetyChecker>()?;
    m.add_function(wrap_pyfunction!(plan_execution, m)?)?;
    Ok(())
}
