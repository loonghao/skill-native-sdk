//! skill-cli: Rust-powered CLI for skill-native-sdk.
//!
//! Public API: `run_cli(args)` → exit code (i32).
//! When compiled with the `python-bindings` feature, also exposes
//! `run_cli` as a `#[pyfunction]` so Python can call it with `sys.argv`.

pub mod args;
pub mod commands;
pub mod display;

use clap::Parser as _;

use args::{Cli, Commands};
use commands::*;

/// Run the skill CLI with the given argument list.
///
/// `args[0]` should be the program name (i.e. pass `sys.argv` directly).
/// Returns an OS exit code: `0` = success, non-zero = failure.
pub fn run_cli(args: &[String]) -> i32 {
    let cli = match Cli::try_parse_from(args) {
        Ok(c) => c,
        Err(e) => {
            // clap prints the error automatically when it exits; here we
            // preserve the intended exit code (0 for --help/--version).
            let code = e.exit_code();
            e.print().ok();
            return code;
        }
    };

    match &cli.command {
        Commands::List { skills_dir, domain } => {
            cmd_list(skills_dir, domain)
        }
        Commands::Describe { skill_name, skills_dir } => {
            cmd_describe(skill_name, skills_dir)
        }
        Commands::Graph { skill_name, skills_dir } => {
            cmd_graph(skill_name, skills_dir)
        }
        Commands::Run { skill_name, tool_name, params, output, skills_dir } => {
            cmd_run(skill_name, tool_name, params, output, skills_dir)
        }
        Commands::Chain { skill_name, entry, params, follow_success, output, skills_dir } => {
            cmd_chain(skill_name, entry, params, *follow_success, output, skills_dir)
        }
    }
}

// ── PyO3 bindings ─────────────────────────────────────────────────────────────

#[cfg(feature = "python-bindings")]
pub mod python {
    use pyo3::prelude::*;

    /// Register `run_cli` into the parent Python module.
    pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add_function(wrap_pyfunction!(py_run_cli, m)?)
    }

    /// `run_cli(args: list[str]) -> int`
    ///
    /// Call from Python as::
    ///
    ///     import sys
    ///     from skill_native_sdk._skill_native_core import run_cli
    ///     sys.exit(run_cli(sys.argv))
    #[pyfunction]
    #[pyo3(name = "run_cli")]
    fn py_run_cli(args: Vec<String>) -> i32 {
        super::run_cli(&args)
    }
}
