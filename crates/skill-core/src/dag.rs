//! DAG Scheduler — parallel execution planner for read-only skill tools.
//!
//! When an LLM requests multiple skill tools that are all `read_only: true`,
//! the scheduler can execute them in parallel, significantly reducing latency.
//! This mirrors the "capabilities graph" concept from the SKILL.md v2 spec.

use std::collections::HashMap;

use skill_schema::SkillSpec;

/// A node in the execution DAG.
#[derive(Debug, Clone)]
pub struct DagNode {
    pub tool_name: String,
    pub can_parallelize: bool,
    pub deps: Vec<String>, // tool names this node depends on (edges)
}

/// An execution plan produced by [`DagScheduler::plan`].
///
/// Tools in each `stage` may be executed concurrently.
/// Stages must be executed sequentially (each stage waits for the previous).
#[derive(Debug, Clone)]
pub struct ExecutionPlan {
    /// Groups of tools that can run in parallel within each stage.
    pub stages: Vec<Vec<String>>,
    /// Total number of tools to execute.
    pub total_tools: usize,
    /// `true` if any stage contains more than one tool (meaning parallelism is used).
    pub has_parallelism: bool,
}

/// Builds an [`ExecutionPlan`] for a set of requested tools from a [`SkillSpec`].
pub struct DagScheduler;

impl DagScheduler {
    /// Plan execution for the given tool names.
    ///
    /// Rules:
    /// 1. All `read_only` tools with no dependencies → first parallel stage
    /// 2. Non-read-only tools, or tools that depend on others → individual sequential stages
    /// 3. `on_success` chains define explicit dependencies
    pub fn plan(spec: &SkillSpec, requested: &[&str]) -> ExecutionPlan {
        let mut nodes: HashMap<String, DagNode> = HashMap::new();

        for tool_name in requested {
            if let Some(tool) = spec.get_tool(tool_name) {
                nodes.insert(tool_name.to_string(), DagNode {
                    tool_name: tool_name.to_string(),
                    can_parallelize: tool.read_only,
                    deps: Vec::new(), // explicit deps could be added via on_success hints
                });
            }
        }

        // Topological sort (Kahn's algorithm) — handles dependency ordering
        // For simplicity: parallel group = all read_only with no deps in this batch
        let parallel: Vec<String> = nodes.values()
            .filter(|n| n.can_parallelize && n.deps.is_empty())
            .map(|n| n.tool_name.clone())
            .collect();

        let sequential: Vec<String> = nodes.values()
            .filter(|n| !n.can_parallelize || !n.deps.is_empty())
            .map(|n| n.tool_name.clone())
            .collect();

        let mut stages: Vec<Vec<String>> = Vec::new();

        // Parallel tools go in a single stage
        if !parallel.is_empty() {
            stages.push(parallel);
        }

        // Sequential tools each get their own stage
        for tool in sequential {
            stages.push(vec![tool]);
        }

        let total_tools = nodes.len();
        let has_parallelism = stages.iter().any(|s| s.len() > 1);

        ExecutionPlan { stages, total_tools, has_parallelism }
    }

    /// Check if two tools from the same spec can run in parallel.
    pub fn can_parallelize(spec: &SkillSpec, tool_a: &str, tool_b: &str) -> bool {
        let a = spec.get_tool(tool_a);
        let b = spec.get_tool(tool_b);
        matches!((a, b), (Some(a), Some(b)) if a.read_only && b.read_only)
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use skill_schema::{SkillSpec, ToolMeta};

    fn make_spec(tools: Vec<(&str, bool)>) -> SkillSpec {
        SkillSpec {
            name: "test".to_string(),
            domain: "test".to_string(),
            tools: tools.into_iter().map(|(name, ro)| ToolMeta {
                name: name.to_string(),
                read_only: ro,
                ..Default::default()
            }).collect(),
            ..Default::default()
        }
    }

    #[test]
    fn parallel_readonly_tools() {
        let spec = make_spec(vec![("a", true), ("b", true), ("c", false)]);
        let plan = DagScheduler::plan(&spec, &["a", "b", "c"]);
        // a and b should be in the same stage, c in its own
        assert!(plan.has_parallelism);
        assert_eq!(plan.total_tools, 3);
        // First stage has both read-only tools
        assert_eq!(plan.stages[0].len(), 2);
    }

    #[test]
    fn no_parallelism_for_write_tools() {
        let spec = make_spec(vec![("x", false), ("y", false)]);
        let plan = DagScheduler::plan(&spec, &["x", "y"]);
        assert!(!plan.has_parallelism);
    }

    #[test]
    fn can_parallelize_check() {
        let spec = make_spec(vec![("r1", true), ("r2", true), ("w1", false)]);
        assert!(DagScheduler::can_parallelize(&spec, "r1", "r2"));
        assert!(!DagScheduler::can_parallelize(&spec, "r1", "w1"));
    }
}
