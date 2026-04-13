//! SKILL.md v2 parser — extracts YAML front-matter from Markdown files.

use std::path::{Path, PathBuf};

use crate::{ParseError, SkillSpec};

// ── YAML extraction ───────────────────────────────────────────────────────────

/// Regex-free front-matter extractor.
/// Returns the YAML string between the first two `---` delimiters.
fn extract_frontmatter(text: &str) -> Option<&str> {
    let text = text.trim_start();
    if !text.starts_with("---") {
        return None;
    }
    let rest = &text[3..];
    // Skip optional newline right after opening ---
    let rest = rest
        .strip_prefix('\n')
        .or_else(|| rest.strip_prefix("\r\n"))
        .unwrap_or(rest);
    // Find closing ---
    let end = rest.find("\n---").or_else(|| rest.find("\r\n---"))?;
    Some(&rest[..end])
}

/// Fenced YAML block extractor (```yaml ... ```).
fn extract_fenced_yaml(text: &str) -> Option<&str> {
    let start_tag = "```yaml\n";
    let alt_tag = "```yml\n";
    let start = text
        .find(start_tag)
        .map(|i| (i, start_tag.len()))
        .or_else(|| text.find(alt_tag).map(|i| (i, alt_tag.len())));
    let (pos, tag_len) = start?;
    let yaml_start = pos + tag_len;
    let end = text[yaml_start..].find("```")?;
    Some(&text[yaml_start..yaml_start + end])
}

// ── Public parse API ──────────────────────────────────────────────────────────

/// Parse a SKILL.md file or directory that contains one.
///
/// - If `path` points to a **file** → parses that file
/// - If `path` points to a **directory** → looks for `SKILL.md` inside
/// - Non-existent path → returns [`ParseError::NotFound`]
pub fn parse_skill_md(path: &Path) -> Result<SkillSpec, ParseError> {
    // Resolve the actual file path
    let file_path: PathBuf = if path.is_file() {
        path.to_owned()
    } else if path.is_dir() {
        let candidate = path.join("SKILL.md");
        if !candidate.exists() {
            return Err(ParseError::NotFound(path.to_owned()));
        }
        candidate
    } else {
        return Err(ParseError::NotFound(path.to_owned()));
    };

    let source_dir = file_path
        .parent()
        .unwrap_or(Path::new("."))
        .to_string_lossy()
        .to_string();

    let text =
        std::fs::read_to_string(&file_path).map_err(|e| ParseError::Io(file_path.clone(), e))?;

    parse_skill_md_str(&text, source_dir)
}

/// Parse SKILL.md from a string (useful for testing and in-memory processing).
pub fn parse_skill_md_str(text: &str, source_dir: String) -> Result<SkillSpec, ParseError> {
    // Try front-matter first, then fenced yaml, then whole-file YAML
    let yaml = if let Some(fm) = extract_frontmatter(text) {
        fm
    } else if let Some(fb) = extract_fenced_yaml(text) {
        fb
    } else {
        // Try to parse the whole text as YAML
        text
    };

    let mut spec: SkillSpec =
        serde_yaml::from_str(yaml).map_err(|e| ParseError::Yaml(e.to_string()))?;

    spec.source_dir = source_dir;
    Ok(spec)
}

/// Recursively scan a directory for SKILL.md files.
///
/// Unlike `parse_skill_md`, this never fails: skills that fail to parse are
/// silently skipped (and a warning is emitted via `eprintln!`).
pub fn scan_and_load(root: &Path) -> Vec<SkillSpec> {
    let mut specs = Vec::new();
    scan_recursive(root, &mut specs);
    specs
}

fn scan_recursive(dir: &Path, acc: &mut Vec<SkillSpec>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            // Check if this directory has a SKILL.md
            let skill_md = path.join("SKILL.md");
            if skill_md.exists() {
                match parse_skill_md(&path) {
                    Ok(spec) => acc.push(spec),
                    Err(e) => eprintln!("[skill-schema] skipping {}: {e}", path.display()),
                }
                // Don't recurse into skill directories — each skill is self-contained
            } else {
                // Recurse into non-skill directories
                scan_recursive(&path, acc);
            }
        }
    }
}
