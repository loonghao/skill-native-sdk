//! PyO3 bindings for skill-schema types.

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::{models::*, parse_skill_md as rs_parse_skill_md, scan_and_load as rs_scan_and_load, ParseError};
use std::path::Path;

// ── PyToolMeta ────────────────────────────────────────────────────────────────

#[pyclass(name = "ToolMeta")]
#[derive(Clone)]
pub struct PyToolMeta(pub ToolMeta);

#[pymethods]
impl PyToolMeta {
    #[getter] fn name(&self) -> &str { &self.0.name }
    #[getter] fn description(&self) -> &str { &self.0.description }
    #[getter] fn source_file(&self) -> Option<&str> { self.0.source_file.as_deref() }
    #[getter] fn read_only(&self) -> bool { self.0.read_only }
    #[getter] fn destructive(&self) -> bool { self.0.destructive }
    #[getter] fn idempotent(&self) -> bool { self.0.idempotent }
    #[getter] fn cost(&self) -> &str { &self.0.cost }
    #[getter] fn latency(&self) -> &str { &self.0.latency }
    #[getter] fn on_success_suggest(&self) -> Vec<String> { self.0.on_success.suggest.clone() }
    #[getter] fn on_error_suggest(&self) -> Vec<String> { self.0.on_error.suggest.clone() }

    fn input_fields<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(py);
        for (k, v) in &self.0.input {
            let fd = PyDict::new(py);
            fd.set_item("type", &v.field_type)?;
            fd.set_item("description", &v.description)?;
            fd.set_item("required", v.required)?;
            d.set_item(k, fd)?;
        }
        Ok(d)
    }

    fn __repr__(&self) -> String {
        format!("ToolMeta(name={:?}, read_only={})", self.0.name, self.0.read_only)
    }
}

// ── PySkillSpec ───────────────────────────────────────────────────────────────

#[pyclass(name = "RustSkillSpec")]
#[derive(Clone)]
pub struct PySkillSpec(pub SkillSpec);

#[pymethods]
impl PySkillSpec {
    #[getter] fn name(&self) -> &str { &self.0.name }
    #[getter] fn domain(&self) -> &str { &self.0.domain }
    #[getter] fn version(&self) -> &str { &self.0.version }
    #[getter] fn description(&self) -> &str { &self.0.description }
    #[getter] fn tags(&self) -> Vec<String> { self.0.tags.clone() }
    #[getter] fn source_dir(&self) -> &str { &self.0.source_dir }
    #[getter] fn runtime_type(&self) -> &str { &self.0.runtime.runtime_type }
    #[getter] fn runtime_entry(&self) -> &str { &self.0.runtime.entry }
    #[getter] fn runtime_interpreter(&self) -> Option<&str> { self.0.runtime.interpreter.as_deref() }
    #[getter] fn perm_network(&self) -> bool { self.0.permissions.network }
    #[getter] fn perm_filesystem(&self) -> &str { &self.0.permissions.filesystem }
    #[getter] fn perm_external_api(&self) -> bool { self.0.permissions.external_api }

    fn tools(&self) -> Vec<PyToolMeta> {
        self.0.tools.iter().map(|t| PyToolMeta(t.clone())).collect()
    }

    fn get_tool(&self, name: &str) -> Option<PyToolMeta> {
        self.0.get_tool(name).map(|t| PyToolMeta(t.clone()))
    }

    fn entry_points(&self) -> Vec<String> {
        self.0.entry_points().iter().map(|s| s.to_string()).collect()
    }

    fn readonly_tools(&self) -> Vec<PyToolMeta> {
        self.0.readonly_tools().into_iter().map(|t| PyToolMeta(t.clone())).collect()
    }

    fn __repr__(&self) -> String {
        format!("RustSkillSpec(name={:?}, tools={})", self.0.name, self.0.tools.len())
    }
}

// ── Python functions ──────────────────────────────────────────────────────────

/// Parse a SKILL.md file or directory. Raises ``FileNotFoundError`` or ``ValueError``
/// on error, returns ``None`` if no SKILL.md was found.
#[pyfunction]
pub fn parse_skill_md(path: &str) -> PyResult<Option<PySkillSpec>> {
    let p = Path::new(path);
    match rs_parse_skill_md(p) {
        Ok(spec) => Ok(Some(PySkillSpec(spec))),
        Err(ParseError::NotFound(_)) => Ok(None),
        Err(ParseError::Yaml(e)) => Err(pyo3::exceptions::PyValueError::new_err(
            format!("SKILL.md YAML parse error: {e}")
        )),
        Err(ParseError::Io(p, e)) => Err(pyo3::exceptions::PyIOError::new_err(
            format!("IO error reading {}: {e}", p.display())
        )),
    }
}

/// Recursively scan *directory* for SKILL.md files and return all parsed specs.
#[pyfunction]
pub fn scan_and_load(directory: &str) -> Vec<PySkillSpec> {
    rs_scan_and_load(Path::new(directory))
        .into_iter()
        .map(PySkillSpec)
        .collect()
}

/// Register all skill-schema types and functions on a PyO3 module.
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyToolMeta>()?;
    m.add_class::<PySkillSpec>()?;
    m.add_function(wrap_pyfunction!(parse_skill_md, m)?)?;
    m.add_function(wrap_pyfunction!(scan_and_load, m)?)?;
    Ok(())
}
