//! PyO3 bindings for skill-runtime.

use pyo3::prelude::*;

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // SubprocessBridge configuration class exposed to Python
    m.add("SUBPROCESS_BRIDGE", "subprocess")?;
    m.add("HTTP_BRIDGE", "http")?;
    m.add("PYTHON_BRIDGE", "python")?;
    Ok(())
}
