//! SafetyChecker — enforces SKILL.md v2 safety semantics at the execution layer.

use skill_schema::ToolMeta;

/// Decision returned by [`SafetyChecker::check`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SafetyDecision {
    /// The tool may be executed immediately.
    Allow,
    /// The tool is destructive — execution requires explicit confirmation.
    RequiresConfirmation(String),
    /// The tool is blocked by the active policy (e.g. external API calls denied).
    Blocked(String),
}

/// Policy configuration for the safety checker.
#[derive(Debug, Clone)]
pub struct SafetyPolicy {
    /// If `true`, destructive tools always require confirmation even when the
    /// caller passes `confirmed = true`.  Useful in read-only environments.
    pub block_destructive: bool,
    /// If `true`, tools with `cost = "external"` are blocked.
    pub block_external_cost: bool,
}

impl Default for SafetyPolicy {
    fn default() -> Self {
        Self {
            block_destructive: false,
            block_external_cost: false,
        }
    }
}

/// Checks a [`ToolMeta`] against a [`SafetyPolicy`] before execution.
#[derive(Debug, Default)]
pub struct SafetyChecker {
    policy: SafetyPolicy,
}

impl SafetyChecker {
    pub fn new(policy: SafetyPolicy) -> Self {
        Self { policy }
    }

    /// Check whether *tool* may be executed.
    ///
    /// `confirmed` — `true` if the caller has explicitly acknowledged the
    /// destructive nature of the tool (e.g. via `__confirmed__=true` in MCP args).
    pub fn check(&self, tool: &ToolMeta, confirmed: bool) -> SafetyDecision {
        // Hard block on external cost if policy says so
        if self.policy.block_external_cost && tool.cost == "external" {
            return SafetyDecision::Blocked(format!(
                "Tool '{}' has cost=external which is blocked by policy", tool.name
            ));
        }

        // Destructive tools
        if tool.destructive {
            if self.policy.block_destructive {
                return SafetyDecision::Blocked(format!(
                    "Tool '{}' is destructive and blocked by policy", tool.name
                ));
            }
            if !confirmed {
                return SafetyDecision::RequiresConfirmation(format!(
                    "⚠️ Tool '{}' is destructive and cannot be undone. \
                     Re-call with __confirmed__=true to proceed.",
                    tool.name
                ));
            }
        }

        SafetyDecision::Allow
    }

    /// `true` if a read-only tool can be safely parallelized.
    pub fn is_parallelizable(&self, tool: &ToolMeta) -> bool {
        tool.read_only
    }

    /// `true` if an idempotent tool's result can be served from cache.
    pub fn is_cacheable(&self, tool: &ToolMeta) -> bool {
        tool.idempotent
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use skill_schema::ToolMeta;

    fn make_tool(destructive: bool, cost: &str) -> ToolMeta {
        ToolMeta {
            name: "test".to_string(),
            destructive,
            cost: cost.to_string(),
            ..Default::default()
        }
    }

    #[test]
    fn allow_safe_tool() {
        let checker = SafetyChecker::default();
        let tool = make_tool(false, "low");
        assert_eq!(checker.check(&tool, false), SafetyDecision::Allow);
    }

    #[test]
    fn requires_confirmation_for_destructive() {
        let checker = SafetyChecker::default();
        let tool = make_tool(true, "low");
        assert!(matches!(checker.check(&tool, false), SafetyDecision::RequiresConfirmation(_)));
        assert_eq!(checker.check(&tool, true), SafetyDecision::Allow);
    }

    #[test]
    fn block_external_cost_by_policy() {
        let checker = SafetyChecker::new(SafetyPolicy { block_external_cost: true, ..Default::default() });
        let tool = make_tool(false, "external");
        assert!(matches!(checker.check(&tool, false), SafetyDecision::Blocked(_)));
    }
}
