//! Command implementations.
//!
//! Discovery strategy (mirrors Codex):
//! 1. `cmd_list` — uses `ScanOutcome.metadata` (fast, no full YAML parse)
//! 2. All other commands — call `meta.load()` only for the target skill (lazy)

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use skill_core::ToolResult;
use skill_runtime::bridge::{BridgeRouter, ExecutionRequest};
use skill_runtime::SubprocessBridge;
use skill_schema::manager::{scan_explicit_roots, SkillsManager};
use skill_schema::models::SkillMetadata;
use skill_schema::SkillSpec;

use crate::args::OutputFormat;
use crate::display::*;

// ── helpers ───────────────────────────────────────────────────────────────────

/// Return the scan outcome for the given `--skills-dir` (or cwd-auto-discovery).
///
/// If `skills_dir` is the default (`./skills`) **and** it doesn't exist on disk
/// we fall back to `SkillsManager::scan_for_cwd` so the layered roots
/// (`.codex/skills/`, `~/.skill-native/skills/`, etc.) are tried automatically.
fn discover(skills_dir: &str) -> Result<Vec<SkillMetadata>, String> {
    let explicit = Path::new(skills_dir);

    let outcome = if explicit.is_dir() {
        // Explicit dir supplied (or default `./skills` exists)
        scan_explicit_roots(&[explicit])
    } else {
        // Fall back to SkillsManager layered discovery from cwd
        let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
        let mgr = SkillsManager::new();
        (*mgr.scan_for_cwd(&cwd, false)).clone()
    };

    if !outcome.errors.is_empty() {
        for e in &outcome.errors {
            eprintln!("{} {}: {}", yellow("warn:"), e.path.display(), e.message);
        }
    }
    Ok(outcome.metadata)
}

/// Find a skill by name inside a metadata list; load the full spec lazily.
fn find_and_load(metadata: &[SkillMetadata], name: &str) -> Result<SkillSpec, String> {
    let meta = metadata
        .iter()
        .find(|m| m.name == name)
        .ok_or_else(|| format!("skill not found: {name}"))?;
    meta.load().map_err(|e| e.to_string())
}

fn parse_params(raw: &Option<String>) -> Result<serde_json::Value, String> {
    match raw {
        None => Ok(serde_json::json!({})),
        Some(s) => serde_json::from_str(s)
            .map_err(|e| format!("invalid params JSON: {e}")),
    }
}

fn print_result(result: &ToolResult, fmt: &OutputFormat) {
    let output = match fmt {
        OutputFormat::Toon => serde_json::to_string(&result.to_toon()).unwrap(),
        OutputFormat::Mcp  => serde_json::to_string(&result.to_mcp()).unwrap(),
        OutputFormat::Json => serde_json::to_string_pretty(
            &serde_json::to_value(result).unwrap()
        ).unwrap(),
    };
    println!("{output}");
}

fn make_router() -> BridgeRouter {
    BridgeRouter::new().register(Box::new(SubprocessBridge::default()))
}

// ── list ──────────────────────────────────────────────────────────────────────
// Uses lightweight SkillMetadata — no full YAML parse required.

pub fn cmd_list(skills_dir: &str, domain: &Option<String>) -> i32 {
    let metadata = match discover(skills_dir) {
        Ok(m) => m, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };
    let filtered: Vec<_> = metadata.iter().filter(|m| {
        domain.as_ref().is_none_or(|d| &m.domain == d)
    }).collect();

    if filtered.is_empty() {
        println!("{}", yellow("No skills found."));
        return 0;
    }

    println!("\n{}", bold(&format!("{:<28} {:<8} {:<8} {:<7}  {}",
        "Name", "Domain", "Version", "Scope", "Description")));
    println!("{}", dim(&"─".repeat(76)));
    for m in &filtered {
        let desc: String = m.description.chars().take(44).collect();
        println!("{:<38} {:<8} {:<8} {:<7}  {}",
            cyan(&m.name), m.domain, m.version, dim(m.scope.as_str()), desc);
    }
    println!();
    0
}

// ── describe ──────────────────────────────────────────────────────────────────

pub fn cmd_describe(skill_name: &str, skills_dir: &str) -> i32 {
    let metadata = match discover(skills_dir) {
        Ok(m) => m, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };
    let spec = match find_and_load(&metadata, skill_name) {
        Ok(s) => s, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };

    println!("\n{} v{}  ({})", bold(&cyan(&spec.name)), spec.version, magenta(&spec.domain));
    println!("  {}", spec.description);
    let tags = if spec.tags.is_empty() { "none".into() } else { spec.tags.join(", ") };
    println!("  {}  {}", dim("Tags:"), tags);
    let interp = spec.runtime.interpreter.as_deref().unwrap_or("-");
    println!("  {}  {} / entry={} / interpreter={}", dim("Runtime:"),
        spec.runtime.runtime_type, spec.runtime.entry, interp);
    println!("  {}  network={}  filesystem={}\n", dim("Permissions:"),
        spec.permissions.network, spec.permissions.filesystem);

    for tool in &spec.tools {
        let mut flags: Vec<String> = Vec::new();
        if tool.read_only   { flags.push(green("read-only")); }
        if tool.destructive { flags.push(red("destructive")); }
        if tool.idempotent  { flags.push(cyan("idempotent")); }
        println!("  {} {}  {}", bold("●"), bold(&tool.name), flags.join("  "));
        println!("    {}", tool.description);
        if !tool.on_success.suggest.is_empty() {
            println!("    {} {:?}", dim("on_success →"), tool.on_success.suggest);
        }
        println!();
    }
    0
}

// ── graph ─────────────────────────────────────────────────────────────────────

pub fn cmd_graph(skill_name: &str, skills_dir: &str) -> i32 {
    let metadata = match discover(skills_dir) {
        Ok(m) => m, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };
    let spec = match find_and_load(&metadata, skill_name) {
        Ok(s) => s, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };

    // Build capability graph
    let entry_points = spec.entry_points();
    let mut graph: HashMap<&str, serde_json::Value> = HashMap::new();
    for tool in &spec.tools {
        graph.insert(&tool.name, serde_json::json!({
            "on_success": tool.on_success.suggest,
            "on_error":   tool.on_error.suggest,
            "read_only":  tool.read_only,
            "idempotent": tool.idempotent,
            "cost":       tool.cost,
        }));
    }

    let out = serde_json::json!({
        "skill":        skill_name,
        "domain":       spec.domain,
        "entry_points": entry_points,
        "graph":        graph,
    });
    println!("{}", serde_json::to_string_pretty(&out).unwrap());
    0
}

// ── run ───────────────────────────────────────────────────────────────────────

pub fn cmd_run(
    skill_name: &str,
    tool_name: &str,
    params_raw: &Option<String>,
    fmt: &OutputFormat,
    skills_dir: &str,
) -> i32 {
    let metadata = match discover(skills_dir) {
        Ok(m) => m, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };
    let spec = match find_and_load(&metadata, skill_name) {
        Ok(s) => s, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };
    let params = match parse_params(params_raw) {
        Ok(p) => p, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };

    let router = make_router();
    let req = ExecutionRequest {
        skill_name: skill_name.to_string(),
        tool_name: tool_name.to_string(),
        params,
        confirmed: false,
    };
    match router.execute(&spec, &req) {
        Ok(resp) => { print_result(&resp.result, fmt); if resp.result.success { 0 } else { 1 } }
        Err(e)   => { eprintln!("{}", red(&e.to_string())); 1 }
    }
}

// ── chain ─────────────────────────────────────────────────────────────────────

pub fn cmd_chain(
    skill_name: &str,
    entry: &str,
    params_raw: &Option<String>,
    follow_success: bool,
    fmt: &OutputFormat,
    skills_dir: &str,
) -> i32 {
    let metadata = match discover(skills_dir) {
        Ok(m) => m, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };
    let spec = match find_and_load(&metadata, skill_name) {
        Ok(s) => s, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };
    let entry_params = match parse_params(params_raw) {
        Ok(p) => p, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };

    let router = make_router();
    let mut current_tool = entry.to_string();
    let mut step = 1usize;

    loop {
        println!("\n{} {} / {}", dim(&format!("Step {step}:")),
            bold(skill_name), bold(&current_tool));

        let params = if step == 1 { entry_params.clone() } else { serde_json::json!({}) };
        let req = ExecutionRequest {
            skill_name: skill_name.to_string(),
            tool_name: current_tool.clone(),
            params,
            confirmed: false,
        };

        let result = match router.execute(&spec, &req) {
            Ok(resp) => resp.result,
            Err(e)   => { eprintln!("{}", red(&e.to_string())); return 1; }
        };

        print_result(&result, fmt);

        if !result.success || !follow_success { break; }

        if let Some(tool_meta) = spec.get_tool(&current_tool) {
            if let Some(next) = tool_meta.on_success.suggest.first() {
                current_tool = next.clone();
                step += 1;
                continue;
            }
        }
        break;
    }
    0
}
