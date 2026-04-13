//! SKILL.md v2 parser — extracts YAML front-matter from Markdown files.
//!
//! Key public functions:
//!
//! | Function | Purpose |
//! |---|---|
//! | [`parse_skill_md`] | Parse a SKILL.md file → [`SkillSpec`] (Repo scope) |
//! | [`parse_skill_md_with_scope`] | Parse with an explicit [`SkillScope`] |
//! | [`parse_skill_md_str`] | Parse from a string (tests / in-memory) |
//! | [`parse_frontmatter_only`] | **Lazy** — reads only `name`/`description`/`domain` |
//! | [`scan_and_load`] | One-shot BFS scan of a single directory root |

use std::collections::{HashSet, VecDeque};
use std::path::{Path, PathBuf};

use crate::models::{ScanError, ScanOutcome, SkillMetadata};
use crate::scope::{SkillRoot, SkillScope};
use crate::{ParseError, SkillSpec};

/// BFS depth limit — mirrors Codex's `MAX_SCAN_DEPTH`.
const MAX_SCAN_DEPTH: usize = 6;
/// Per-root directory budget — mirrors Codex's `MAX_SKILLS_DIRS_PER_ROOT`.
const MAX_SKILLS_DIRS_PER_ROOT: usize = 2000;

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

/// Parse a SKILL.md file or directory (defaults to [`SkillScope::Repo`]).
///
/// - If `path` points to a **file** → parses that file.
/// - If `path` points to a **directory** → looks for `SKILL.md` inside.
/// - Non-existent path → returns [`ParseError::NotFound`].
pub fn parse_skill_md(path: &Path) -> Result<SkillSpec, ParseError> {
    parse_skill_md_with_scope(path, SkillScope::Repo)
}

/// Like [`parse_skill_md`] but also sets the [`SkillScope`] on the result.
pub fn parse_skill_md_with_scope(path: &Path, scope: SkillScope) -> Result<SkillSpec, ParseError> {
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

    let yaml = pick_yaml(&text);
    let mut spec: SkillSpec =
        serde_yaml::from_str(yaml).map_err(|e| ParseError::Yaml(e.to_string()))?;

    spec.source_dir = source_dir;
    spec.scope = scope;
    spec.path_to_skill_md = file_path;
    Ok(spec)
}

/// Parse SKILL.md from a string (useful for testing and in-memory processing).
///
/// Scope defaults to [`SkillScope::Repo`] and `path_to_skill_md` is left empty.
pub fn parse_skill_md_str(text: &str, source_dir: String) -> Result<SkillSpec, ParseError> {
    let yaml = pick_yaml(text);
    let mut spec: SkillSpec =
        serde_yaml::from_str(yaml).map_err(|e| ParseError::Yaml(e.to_string()))?;
    spec.source_dir = source_dir;
    Ok(spec)
}

/// **Lazy parse** — reads only `name`, `description`, `domain`, `version`, and
/// `tags` from the frontmatter, skipping full tool-list parsing.
///
/// This is the fast path used by [`crate::manager::SkillsManager`] during the
/// initial discovery scan (mirrors Codex's two-phase approach).
pub fn parse_frontmatter_only(
    path: &Path,
    scope: SkillScope,
) -> Result<SkillMetadata, ParseError> {
    let text =
        std::fs::read_to_string(path).map_err(|e| ParseError::Io(path.to_owned(), e))?;

    let yaml = pick_yaml(&text);

    #[derive(serde::Deserialize, Default)]
    struct Minimal {
        #[serde(default)]
        name: String,
        #[serde(default)]
        description: String,
        #[serde(default)]
        domain: String,
        #[serde(default)]
        version: String,
        #[serde(default)]
        tags: Vec<String>,
    }

    let m: Minimal =
        serde_yaml::from_str(yaml).map_err(|e| ParseError::Yaml(e.to_string()))?;

    let source_dir = path
        .parent()
        .unwrap_or(Path::new("."))
        .to_string_lossy()
        .to_string();

    Ok(SkillMetadata {
        name: m.name,
        description: m.description,
        domain: m.domain,
        version: m.version,
        tags: m.tags,
        scope,
        path_to_skill_md: path.to_owned(),
        source_dir,
    })
}

/// Scan a single directory root for SKILL.md files (BFS, all as `Repo` scope).
///
/// This is the **backward-compatible** convenience function. For multi-root
/// layered discovery use [`crate::manager::SkillsManager`] instead.
pub fn scan_and_load(root: &Path) -> Vec<SkillSpec> {
    if !root.exists() {
        return Vec::new();
    }
    let single_root = vec![SkillRoot::repo(root)];
    let outcome = load_skills_from_roots(single_root);
    // Lazily promote metadata → full SkillSpec
    outcome
        .metadata
        .iter()
        .filter_map(|m| match m.load() {
            Ok(s) => Some(s),
            Err(e) => {
                eprintln!("[skill-schema] failed to load {}: {e}", m.path_to_skill_md.display());
                None
            }
        })
        .collect()
}

/// Load skills from an ordered list of [`SkillRoot`]s.
///
/// Rules (same as Codex):
/// 1. BFS traversal with depth ≤ `MAX_SCAN_DEPTH` and ≤ `MAX_SKILLS_DIRS_PER_ROOT` dirs/root.
/// 2. Hidden directories (starting with `.`) are skipped.
/// 3. A directory containing `SKILL.md` is **not** recursed into.
/// 4. **Deduplication** by canonical path — the first root to claim a path wins.
/// 5. Results sorted by `scope.rank()` then `name`.
pub fn load_skills_from_roots(roots: Vec<SkillRoot>) -> ScanOutcome {
    let mut metadata: Vec<SkillMetadata> = Vec::new();
    let mut errors: Vec<ScanError> = Vec::new();
    let mut seen: HashSet<PathBuf> = HashSet::new();

    for root in &roots {
        if root.path.is_dir() {
            discover_under_root(&root.path, root.scope, &mut metadata, &mut errors, &mut seen);
        }
    }

    // Sort: Repo(0) > User(1) > System(2), then alphabetically by name
    metadata.sort_by(|a, b| {
        a.scope
            .rank()
            .cmp(&b.scope.rank())
            .then_with(|| a.name.cmp(&b.name))
    });

    ScanOutcome { metadata, errors }
}

// ── BFS discovery ─────────────────────────────────────────────────────────────

/// BFS traversal of a single root directory — populates `metadata` and `errors`.
pub(crate) fn discover_under_root(
    root: &Path,
    scope: SkillScope,
    metadata: &mut Vec<SkillMetadata>,
    errors: &mut Vec<ScanError>,
    seen: &mut HashSet<PathBuf>,
) {
    let mut queue: VecDeque<(PathBuf, usize)> = VecDeque::new();
    queue.push_back((root.to_owned(), 0));
    let mut dirs_visited = 0usize;

    while let Some((dir, depth)) = queue.pop_front() {
        if depth > MAX_SCAN_DEPTH || dirs_visited >= MAX_SKILLS_DIRS_PER_ROOT {
            break;
        }
        dirs_visited += 1;

        let Ok(read_dir) = std::fs::read_dir(&dir) else {
            continue;
        };

        for entry in read_dir.flatten() {
            let name_os = entry.file_name();
            let name = name_os.to_string_lossy();

            // Skip hidden files / directories (`.git`, `.venv`, etc.)
            if name.starts_with('.') {
                continue;
            }

            let path = entry.path();
            if !path.is_dir() {
                continue;
            }

            let skill_md = path.join("SKILL.md");
            if skill_md.exists() {
                // Dedup by canonical path so symlinks don't double-count
                let canonical =
                    skill_md.canonicalize().unwrap_or_else(|_| skill_md.clone());
                if seen.insert(canonical) {
                    match parse_frontmatter_only(&skill_md, scope) {
                        Ok(m) => metadata.push(m),
                        Err(e) => errors.push(ScanError {
                            path: skill_md,
                            message: e.to_string(),
                        }),
                    }
                }
                // Do NOT recurse into the skill directory itself
            } else {
                queue.push_back((path, depth + 1));
            }
        }
    }
}

// ── Internal helpers ──────────────────────────────────────────────────────────

/// Pick the best YAML snippet from a SKILL.md text buffer.
fn pick_yaml(text: &str) -> &str {
    if let Some(fm) = extract_frontmatter(text) {
        fm
    } else if let Some(fb) = extract_fenced_yaml(text) {
        fb
    } else {
        text
    }
}
