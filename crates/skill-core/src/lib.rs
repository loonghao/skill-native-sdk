//! skill-core — ToolResult, SafetyChecker, ResultCache, DAG scheduler.

pub mod cache;
pub mod dag;
pub mod result;
pub mod safety;

#[cfg(feature = "python-bindings")]
pub mod python;

pub use cache::{CacheKey, ResultCache};
pub use dag::{DagScheduler, ExecutionPlan};
pub use result::ToolResult;
pub use safety::{SafetyChecker, SafetyDecision, SafetyPolicy};

#[cfg(test)]
mod integration_tests {
    use super::*;
    use skill_schema::{SkillSpec, ToolMeta};

    fn make_spec_with_tools(read_only: &[(&str, bool)]) -> SkillSpec {
        SkillSpec {
            name: "test".to_string(),
            tools: read_only.iter().map(|(n, ro)| ToolMeta {
                name: n.to_string(),
                read_only: *ro,
                idempotent: *ro,
                ..Default::default()
            }).collect(),
            ..Default::default()
        }
    }

    #[test]
    fn cache_idempotent_tool_result() {
        let cache = ResultCache::new(10);
        let params = serde_json::json!({"object": "pCube1"});
        let key = CacheKey::new("maya-anim", "get_keyframes", &params);

        assert!(cache.get(&key).is_none(), "cache should start empty");

        let result = ToolResult::ok("frames: [1, 24]")
            .with_next(vec!["bake_simulation".to_string()]);
        cache.insert(key.clone(), result);

        let cached = cache.get(&key).unwrap();
        assert!(cached.success);
        assert_eq!(cached.next_actions, vec!["bake_simulation"]);
    }

    #[test]
    fn dag_plan_parallel_reads() {
        let spec = make_spec_with_tools(&[("get_a", true), ("get_b", true), ("write_c", false)]);
        let plan = DagScheduler::plan(&spec, &["get_a", "get_b", "write_c"]);

        // get_a and get_b are both read-only → should be in the same parallel stage
        assert!(plan.has_parallelism);
        let parallel_stage = plan.stages.iter().find(|s| s.len() > 1).unwrap();
        assert!(parallel_stage.contains(&"get_a".to_string()));
        assert!(parallel_stage.contains(&"get_b".to_string()));
    }

    #[test]
    fn tool_result_toon_format() {
        let r = ToolResult::ok("done").with_next(vec!["next_step".to_string()]);
        let toon = r.to_toon();
        assert_eq!(toon["ok"], true);
        assert_eq!(toon["msg"], "done");
        assert_eq!(toon["next"], serde_json::json!(["next_step"]));
    }

    #[test]
    fn tool_result_mcp_format() {
        let r = ToolResult::fail("oops");
        let mcp = r.to_mcp();
        assert_eq!(mcp["type"], "tool_result");
        assert_eq!(mcp["isError"], true);
    }
}
