//! Skill discovery scope and root definitions.
//!
//! Mirrors the `SkillScope` / `SkillRoot` design from codex-rs, adapted for
//! the skill-native-sdk DCC toolchain context.

use std::path::PathBuf;

// ── SkillScope ────────────────────────────────────────────────────────────────

/// Priority level of a skill discovery root.
///
/// Lower numeric value = higher priority (Repo wins over User wins over System).
///
/// | Scope  | Typical paths                                 |
/// |--------|-----------------------------------------------|
/// | Repo   | `.codex/skills/`, `skills/` (nearest git root)|
/// | User   | `~/.skill-native/skills/`                     |
/// | System | future: embedded built-in skills              |
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
#[derive(serde::Serialize, serde::Deserialize)]
pub enum SkillScope {
    /// Project / repository level — highest priority.
    Repo = 0,
    /// User-global level.
    User = 1,
    /// Embedded / system level — lowest priority.
    System = 2,
}

impl SkillScope {
    /// Numeric rank: smaller = higher priority (Repo = 0).
    #[inline]
    pub fn rank(self) -> u8 {
        self as u8
    }

    /// Human-readable ASCII label used in CLI output.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Repo   => "repo",
            Self::User   => "user",
            Self::System => "system",
        }
    }
}

impl Default for SkillScope {
    fn default() -> Self {
        Self::Repo
    }
}

impl std::fmt::Display for SkillScope {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

// ── SkillRoot ─────────────────────────────────────────────────────────────────

/// A directory to scan for SKILL.md files, together with its priority scope.
#[derive(Debug, Clone)]
pub struct SkillRoot {
    /// Absolute path to the directory.
    pub path: PathBuf,
    /// Priority scope of this root.
    pub scope: SkillScope,
}

impl SkillRoot {
    pub fn new(path: impl Into<PathBuf>, scope: SkillScope) -> Self {
        Self { path: path.into(), scope }
    }

    /// Convenience constructor for Repo-scope roots.
    pub fn repo(path: impl Into<PathBuf>) -> Self {
        Self::new(path, SkillScope::Repo)
    }

    /// Convenience constructor for User-scope roots.
    pub fn user(path: impl Into<PathBuf>) -> Self {
        Self::new(path, SkillScope::User)
    }
}
