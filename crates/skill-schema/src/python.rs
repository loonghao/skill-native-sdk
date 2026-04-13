//! PyO3 bindings for skill-schema types.

use std::path::Path;

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::manager::SkillsManager;
use crate::models::*;
use crate::scope::SkillScope;
use crate::{
    parse_skill_md as rs_parse_skill_md, scan_and_load as rs_scan_and_load, ParseError,
};

// ── PyToolMeta ────────────────────────────────────────────────────────────────

#[pyclass(name = "ToolMeta")]
#[derive(Clone)]
pub struct PyToolMeta(pub ToolMeta);

#[pymethods]
impl PyToolMeta {
    #[getter]
    fn name(&self) -> &str {
        &self.0.name
    }
    #[getter]
    fn description(&self) -> &str {
        &self.0.description
    }
    #[getter]
    fn source_file(&self) -> Option<&str> {
        self.0.source_file.as_deref()
    }
    #[getter]
    fn read_only(&self) -> bool {
        self.0.read_only
    }
    #[getter]
    fn destructive(&self) -> bool {
        self.0.destructive
    }
    #[getter]
    fn idempotent(&self) -> bool {
        self.0.idempotent
    }
    #[getter]
    fn cost(&self) -> &str {
        &self.0.cost
    }
    #[getter]
    fn latency(&self) -> &str {
        &self.0.latency
    }
    #[getter]
    fn on_success_suggest(&self) -> Vec<String> {
        self.0.on_success.suggest.clone()
    }
    #[getter]
    fn on_error_suggest(&self) -> Vec<String> {
        self.0.on_error.suggest.clone()
    }

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
        format!(
            "ToolMeta(name={:?}, read_only={})",
            self.0.name, self.0.read_only
        )
    }
}

// ── PySkillSpec ───────────────────────────────────────────────────────────────

#[pyclass(name = "RustSkillSpec")]
#[derive(Clone)]
pub struct PySkillSpec(pub SkillSpec);

#[pymethods]
impl PySkillSpec {
    #[getter]
    fn name(&self) -> &str {
        &self.0.name
    }
    #[getter]
    fn domain(&self) -> &str {
        &self.0.domain
    }
    #[getter]
    fn version(&self) -> &str {
        &self.0.version
    }
    #[getter]
    fn description(&self) -> &str {
        &self.0.description
    }
    #[getter]
    fn tags(&self) -> Vec<String> {
        self.0.tags.clone()
    }
    #[getter]
    fn source_dir(&self) -> &str {
        &self.0.source_dir
    }
    #[getter]
    fn scope(&self) -> PySkillScope {
        PySkillScope(self.0.scope)
    }
    #[getter]
    fn path_to_skill_md(&self) -> String {
        self.0.path_to_skill_md.to_string_lossy().into_owned()
    }
    #[getter]
    fn runtime_type(&self) -> &str {
        &self.0.runtime.runtime_type
    }
    #[getter]
    fn runtime_entry(&self) -> &str {
        &self.0.runtime.entry
    }
    #[getter]
    fn runtime_interpreter(&self) -> Option<&str> {
        self.0.runtime.interpreter.as_deref()
    }
    #[getter]
    fn perm_network(&self) -> bool {
        self.0.permissions.network
    }
    #[getter]
    fn perm_filesystem(&self) -> &str {
        &self.0.permissions.filesystem
    }
    #[getter]
    fn perm_external_api(&self) -> bool {
        self.0.permissions.external_api
    }

    fn tools(&self) -> Vec<PyToolMeta> {
        self.0.tools.iter().map(|t| PyToolMeta(t.clone())).collect()
    }

    fn get_tool(&self, name: &str) -> Option<PyToolMeta> {
        self.0.get_tool(name).map(|t| PyToolMeta(t.clone()))
    }

    fn entry_points(&self) -> Vec<String> {
        self.0
            .entry_points()
            .iter()
            .map(|s| s.to_string())
            .collect()
    }

    fn readonly_tools(&self) -> Vec<PyToolMeta> {
        self.0
            .readonly_tools()
            .into_iter()
            .map(|t| PyToolMeta(t.clone()))
            .collect()
    }

    fn __repr__(&self) -> String {
        format!(
            "RustSkillSpec(name={:?}, tools={})",
            self.0.name,
            self.0.tools.len()
        )
    }
}

// ── PySkillScope ──────────────────────────────────────────────────────────────

#[pyclass(name = "SkillScope")]
#[derive(Clone)]
pub struct PySkillScope(pub SkillScope);

#[pymethods]
impl PySkillScope {
    /// "repo" | "user" | "system"
    fn as_str(&self) -> &'static str { self.0.as_str() }
    fn rank(&self) -> u8 { self.0.rank() }
    fn __repr__(&self) -> String { format!("SkillScope.{}", self.0.as_str().to_uppercase()) }
    fn __str__(&self) -> &'static str { self.0.as_str() }
}

// ── PySkillMetadata ───────────────────────────────────────────────────────────

#[pyclass(name = "SkillMetadata")]
#[derive(Clone)]
pub struct PySkillMetadata(pub SkillMetadata);

#[pymethods]
impl PySkillMetadata {
    #[getter] fn name(&self) -> &str { &self.0.name }
    #[getter] fn description(&self) -> &str { &self.0.description }
    #[getter] fn domain(&self) -> &str { &self.0.domain }
    #[getter] fn version(&self) -> &str { &self.0.version }
    #[getter] fn tags(&self) -> Vec<String> { self.0.tags.clone() }
    #[getter] fn scope(&self) -> PySkillScope { PySkillScope(self.0.scope) }
    #[getter] fn path_to_skill_md(&self) -> String {
        self.0.path_to_skill_md.to_string_lossy().into_owned()
    }
    #[getter] fn source_dir(&self) -> &str { &self.0.source_dir }

    /// Lazily load the full ``RustSkillSpec`` from disk.
    fn load(&self) -> PyResult<PySkillSpec> {
        self.0.load().map(PySkillSpec).map_err(parse_err_to_py)
    }

    fn __repr__(&self) -> String {
        format!("SkillMetadata(name={:?}, scope={})", self.0.name, self.0.scope)
    }
}

// ── PyScanError ───────────────────────────────────────────────────────────────

#[pyclass(name = "ScanError")]
#[derive(Clone)]
pub struct PyScanError(pub ScanError);

#[pymethods]
impl PyScanError {
    #[getter] fn path(&self) -> String { self.0.path.to_string_lossy().into_owned() }
    #[getter] fn message(&self) -> &str { &self.0.message }
    fn __repr__(&self) -> String {
        format!("ScanError(path={:?}, message={:?})", self.0.path, self.0.message)
    }
}

// ── PyScanOutcome ─────────────────────────────────────────────────────────────

#[pyclass(name = "ScanOutcome")]
#[derive(Clone)]
pub struct PyScanOutcome(pub std::sync::Arc<ScanOutcome>);

#[pymethods]
impl PyScanOutcome {
    /// Lightweight metadata records — one per discovered skill.
    #[getter]
    fn metadata(&self) -> Vec<PySkillMetadata> {
        self.0.metadata.iter().map(|m| PySkillMetadata(m.clone())).collect()
    }

    /// Skills that failed to parse during discovery.
    #[getter]
    fn errors(&self) -> Vec<PyScanError> {
        self.0.errors.iter().map(|e| PyScanError(e.clone())).collect()
    }

    fn __len__(&self) -> usize { self.0.len() }
    fn __repr__(&self) -> String {
        format!("ScanOutcome(skills={}, errors={})", self.0.len(), self.0.errors.len())
    }

    /// Find a skill by name.
    fn find(&self, name: &str) -> Option<PySkillMetadata> {
        self.0.find(name).map(|m| PySkillMetadata(m.clone()))
    }
}

// ── PySkillsManager ───────────────────────────────────────────────────────────

/// Progressive skill discovery manager with layered roots and cwd-keyed cache.
///
/// Example::
///
///     from skill_native_sdk._skill_native_core import SkillsManager
///     mgr = SkillsManager()
///     outcome = mgr.scan_for_cwd(".")
///     for meta in outcome.metadata:
///         print(meta.scope, meta.name, meta.description)
///         spec = meta.load()          # lazy — reads full YAML only now
///         print(len(spec.tools()), "tools")
#[pyclass(name = "SkillsManager", unsendable)]
pub struct PySkillsManager {
    inner: SkillsManager,
}

#[pymethods]
impl PySkillsManager {
    #[new]
    fn new() -> Self {
        Self { inner: SkillsManager::new() }
    }

    /// Scan for skills visible from *cwd*.
    ///
    /// Roots checked (Repo > User):
    /// - ``{cwd}/.codex/skills/`` and ``{cwd}/skills/`` (walks up to git root)
    /// - ``~/.skill-native/skills/``
    #[pyo3(signature = (cwd, force_reload = false))]
    fn scan_for_cwd(&self, cwd: &str, force_reload: bool) -> PyScanOutcome {
        let p = std::path::Path::new(cwd);
        PyScanOutcome(self.inner.scan_for_cwd(p, force_reload))
    }

    /// Lazily load the full ``RustSkillSpec`` from a SKILL.md path.
    fn load_skill(&self, path: &str) -> PyResult<PySkillSpec> {
        self.inner
            .load_skill(std::path::Path::new(path))
            .map(PySkillSpec)
            .map_err(parse_err_to_py)
    }

    /// Invalidate the discovery cache.
    fn clear_cache(&self) {
        self.inner.clear_cache();
    }
}

// ── Shared error helper ───────────────────────────────────────────────────────

fn parse_err_to_py(e: ParseError) -> PyErr {
    match e {
        ParseError::NotFound(p) => pyo3::exceptions::PyFileNotFoundError::new_err(
            format!("SKILL.md not found: {}", p.display()),
        ),
        ParseError::Yaml(msg) => {
            pyo3::exceptions::PyValueError::new_err(format!("YAML parse error: {msg}"))
        }
        ParseError::Io(p, io) => pyo3::exceptions::PyIOError::new_err(format!(
            "IO error reading {}: {io}",
            p.display()
        )),
    }
}

// ── Python functions ──────────────────────────────────────────────────────────

/// Parse a SKILL.md file or directory. Returns ``None`` if not found.
#[pyfunction]
pub fn parse_skill_md(path: &str) -> PyResult<Option<PySkillSpec>> {
    match rs_parse_skill_md(Path::new(path)) {
        Ok(spec) => Ok(Some(PySkillSpec(spec))),
        Err(ParseError::NotFound(_)) => Ok(None),
        Err(e) => Err(parse_err_to_py(e)),
    }
}

/// One-shot BFS scan of *directory*; returns all parsed full specs.
///
/// For progressive (lazy) loading use :class:`SkillsManager` instead.
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
    m.add_class::<PySkillScope>()?;
    m.add_class::<PySkillMetadata>()?;
    m.add_class::<PyScanError>()?;
    m.add_class::<PyScanOutcome>()?;
    m.add_class::<PySkillsManager>()?;
    m.add_function(wrap_pyfunction!(parse_skill_md, m)?)?;
    m.add_function(wrap_pyfunction!(scan_and_load, m)?)?;
    Ok(())
}
