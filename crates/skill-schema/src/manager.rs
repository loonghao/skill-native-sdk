//! Progressive skill discovery manager with layered roots and cwd-keyed cache.
//!
//! # Design (mirrors `codex-rs/core-skills/src/manager.rs`)
//!
//! ```text
//! scan_for_cwd(cwd, force_reload=false)
//!   │
//!   ├─ cache hit?  ──────────────────────────────────► Arc<ScanOutcome>
//!   │
//!   └─ cache miss:
//!       build_skill_roots(cwd)
//!         ├─ Repo: walk cwd → git-root, collect .codex/skills/ + skills/
//!         └─ User: $SKILL_NATIVE_HOME/skills/ or ~/.skill-native/skills/
//!       load_skills_from_roots(roots)   ← BFS + dedup + sort
//!       insert into cache
//!       ──────────────────────────────────────────────► Arc<ScanOutcome>
//! ```

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, RwLock};

use crate::models::ScanOutcome;
use crate::parser::load_skills_from_roots;
use crate::scope::{SkillRoot, SkillScope};
use crate::{ParseError, SkillSpec};

// ── SkillsManager ─────────────────────────────────────────────────────────────

/// Thread-safe, cwd-keyed cache for progressive skill discovery.
///
/// Create one per process (or per session) and reuse across calls.
#[derive(Default)]
pub struct SkillsManager {
    /// Maps canonical cwd → scan result.
    cache: RwLock<HashMap<PathBuf, Arc<ScanOutcome>>>,
}

impl SkillsManager {
    pub fn new() -> Self {
        Self::default()
    }

    /// Discover all skills visible from `cwd`, using the layered root strategy.
    ///
    /// Results are cached; pass `force_reload = true` to bypass the cache
    /// (e.g. after the user adds a new skill).
    pub fn scan_for_cwd(&self, cwd: &Path, force_reload: bool) -> Arc<ScanOutcome> {
        let canonical = cwd.canonicalize().unwrap_or_else(|_| cwd.to_owned());

        if !force_reload {
            if let Ok(cache) = self.cache.read() {
                if let Some(outcome) = cache.get(&canonical) {
                    return outcome.clone();
                }
            }
        }

        let roots = self.build_skill_roots(&canonical);
        let outcome = Arc::new(load_skills_from_roots(roots));

        if let Ok(mut cache) = self.cache.write() {
            cache.insert(canonical, outcome.clone());
        }
        outcome
    }

    /// Lazily load the full [`SkillSpec`] from a `SKILL.md` path.
    ///
    /// Scope defaults to [`SkillScope::Repo`]; prefer
    /// [`crate::models::SkillMetadata::load`] when you have a metadata record
    /// (it preserves the original scope).
    pub fn load_skill(&self, path: &Path) -> Result<SkillSpec, ParseError> {
        crate::parser::parse_skill_md(path)
    }

    /// Invalidate the entire in-process cache.
    pub fn clear_cache(&self) {
        if let Ok(mut cache) = self.cache.write() {
            cache.clear();
        }
    }

    // ── Root building ─────────────────────────────────────────────────────────

    fn build_skill_roots(&self, cwd: &Path) -> Vec<SkillRoot> {
        let mut roots: Vec<SkillRoot> = Vec::new();

        // Repo scope — walk cwd → git root, collect candidate skill dirs.
        // cwd-nearest directories are added first (highest Repo priority).
        let git_root = find_git_root(cwd);
        let search_top = git_root.as_deref().unwrap_or(cwd);

        let mut dir = cwd;
        loop {
            for candidate in [".codex/skills", "skills"] {
                let p = dir.join(candidate);
                if p.is_dir() {
                    roots.push(SkillRoot::repo(&p));
                }
            }
            if dir == search_top {
                break;
            }
            match dir.parent() {
                Some(parent) => dir = parent,
                None => break,
            }
        }

        // User scope — $SKILL_NATIVE_HOME/skills/ or ~/.skill-native/skills/
        if let Some(user_dir) = user_skills_dir() {
            if user_dir.is_dir() {
                roots.push(SkillRoot::user(user_dir));
            }
        }

        roots
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/// Walk up from `cwd` looking for a `.git` directory.
/// Returns the first ancestor that contains `.git`, or `None`.
pub fn find_git_root(cwd: &Path) -> Option<PathBuf> {
    let mut dir = cwd;
    loop {
        if dir.join(".git").exists() {
            return Some(dir.to_owned());
        }
        dir = dir.parent()?;
    }
}

/// Resolve the user-level skills directory.
///
/// Priority:
/// 1. `$SKILL_NATIVE_HOME/skills/`
/// 2. `$HOME/.skill-native/skills/`  (Unix)
/// 3. `%USERPROFILE%\.skill-native\skills\`  (Windows)
pub fn user_skills_dir() -> Option<PathBuf> {
    if let Ok(home) = std::env::var("SKILL_NATIVE_HOME") {
        return Some(PathBuf::from(home).join("skills"));
    }
    let home = std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .ok()?;
    Some(PathBuf::from(home).join(".skill-native").join("skills"))
}

/// Convenience: build roots for a given cwd without a `SkillsManager` instance.
pub fn skill_roots_for_cwd(cwd: &Path) -> Vec<SkillRoot> {
    SkillsManager::new().build_skill_roots(cwd)
}

/// Build `ScanOutcome` from an explicit list of [`SkillScope::Repo`] directories.
///
/// Useful when the caller already knows the roots (e.g. CLI `--skills-dir`).
pub fn scan_explicit_roots(dirs: &[&Path]) -> ScanOutcome {
    let roots: Vec<SkillRoot> = dirs
        .iter()
        .filter(|p| p.is_dir())
        .map(|p| SkillRoot::new(*p, SkillScope::Repo))
        .collect();
    load_skills_from_roots(roots)
}
