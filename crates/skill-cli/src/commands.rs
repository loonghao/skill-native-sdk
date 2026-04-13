//! Command implementations.

use std::collections::HashMap;
use std::path::Path;

use skill_core::ToolResult;
use skill_runtime::bridge::{BridgeRouter, ExecutionRequest};
use skill_runtime::SubprocessBridge;
use skill_schema::{scan_and_load, SkillSpec};

use crate::args::OutputFormat;
use crate::display::*;

// ── helpers ───────────────────────────────────────────────────────────────────

fn load_skills(skills_dir: &str) -> Result<Vec<SkillSpec>, String> {
    let p = Path::new(skills_dir);
    if !p.exists() {
        return Err(format!("skills directory not found: {skills_dir}"));
    }
    Ok(scan_and_load(p))
}

fn find_skill<'a>(specs: &'a [SkillSpec], name: &str) -> Result<&'a SkillSpec, String> {
    specs.iter().find(|s| s.name == name)
        .ok_or_else(|| format!("skill not found: {name}"))
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

pub fn cmd_list(skills_dir: &str, domain: &Option<String>) -> i32 {
    let specs = match load_skills(skills_dir) {
        Ok(s) => s, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };
    let specs: Vec<_> = specs.iter().filter(|s| {
        domain.as_ref().is_none_or(|d| &s.domain == d)
    }).collect();

    if specs.is_empty() {
        println!("{}", yellow("No skills found."));
        return 0;
    }

    println!("\n{}", bold(&format!("{:<28} {:<12} {:<8} {:>5}  {}",
        "Name", "Domain", "Version", "Tools", "Description")));
    println!("{}", dim(&"─".repeat(72)));
    for s in &specs {
        let desc: String = s.description.chars().take(40).collect();
        println!("{:<38} {:<12} {:<8} {:>5}  {}",
            cyan(&s.name), s.domain, s.version, s.tools.len(), desc);
    }
    println!();
    0
}

// ── describe ──────────────────────────────────────────────────────────────────

pub fn cmd_describe(skill_name: &str, skills_dir: &str) -> i32 {
    let specs = match load_skills(skills_dir) {
        Ok(s) => s, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };
    let spec = match find_skill(&specs, skill_name) {
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
    let specs = match load_skills(skills_dir) {
        Ok(s) => s, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };
    let spec = match find_skill(&specs, skill_name) {
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
    let specs = match load_skills(skills_dir) {
        Ok(s) => s, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };
    let spec = match find_skill(&specs, skill_name) {
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
    match router.execute(spec, &req) {
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
    let specs = match load_skills(skills_dir) {
        Ok(s) => s, Err(e) => { eprintln!("{}", red(&e)); return 1; }
    };
    let spec = match find_skill(&specs, skill_name) {
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

        let result = match router.execute(spec, &req) {
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
