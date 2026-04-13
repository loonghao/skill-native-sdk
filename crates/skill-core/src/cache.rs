//! ResultCache — memoization for idempotent skill tools.
//!
//! Idempotent tools (`idempotent: true` in SKILL.md) always produce the same
//! output for the same input. The cache stores results keyed by
//! `(skill_name, tool_name, params_json)` so repeated calls are served from
//! memory without re-executing the underlying script.

use std::hash::Hash;

use dashmap::DashMap;

use crate::ToolResult;

/// Cache key: (skill_name, tool_name, params_json_sorted).
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct CacheKey {
    pub skill: String,
    pub tool: String,
    /// Sorted, canonicalized JSON of the input parameters.
    pub params_json: String,
}

impl CacheKey {
    pub fn new(skill: &str, tool: &str, params: &serde_json::Value) -> Self {
        // Canonicalize by sorting keys recursively
        let canonical = canonicalize(params);
        Self {
            skill: skill.to_string(),
            tool: tool.to_string(),
            params_json: serde_json::to_string(&canonical).unwrap_or_default(),
        }
    }
}

/// Recursively sort object keys for canonical JSON representation.
fn canonicalize(v: &serde_json::Value) -> serde_json::Value {
    match v {
        serde_json::Value::Object(map) => {
            let mut sorted: serde_json::Map<String, serde_json::Value> = serde_json::Map::new();
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            for k in keys {
                sorted.insert(k.clone(), canonicalize(&map[k]));
            }
            serde_json::Value::Object(sorted)
        }
        serde_json::Value::Array(arr) => {
            serde_json::Value::Array(arr.iter().map(canonicalize).collect())
        }
        other => other.clone(),
    }
}

/// Thread-safe, lock-free result cache backed by [`DashMap`].
pub struct ResultCache {
    inner: DashMap<CacheKey, ToolResult>,
    max_size: usize,
}

impl ResultCache {
    pub fn new(max_size: usize) -> Self {
        Self {
            inner: DashMap::new(),
            max_size,
        }
    }

    /// Look up a cached result. Returns `None` on cache miss.
    pub fn get(&self, key: &CacheKey) -> Option<ToolResult> {
        self.inner.get(key).map(|r| r.clone())
    }

    /// Store a result. If the cache is full, a random entry is evicted
    /// (cheap, acceptable for the expected small cache sizes in skill execution).
    pub fn insert(&self, key: CacheKey, result: ToolResult) {
        if self.inner.len() >= self.max_size {
            // Simple eviction: remove first entry found
            if let Some(first_key) = self.inner.iter().next().map(|e| e.key().clone()) {
                self.inner.remove(&first_key);
            }
        }
        self.inner.insert(key, result);
    }

    pub fn invalidate(&self, key: &CacheKey) {
        self.inner.remove(key);
    }

    pub fn clear(&self) {
        self.inner.clear();
    }

    pub fn len(&self) -> usize {
        self.inner.len()
    }

    pub fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }
}

impl Default for ResultCache {
    fn default() -> Self {
        Self::new(256)
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cache_hit_and_miss() {
        let cache = ResultCache::new(10);
        let key = CacheKey::new("skill-a", "tool-x", &serde_json::json!({"x": 1}));
        assert!(cache.get(&key).is_none());

        cache.insert(key.clone(), ToolResult::ok("cached result"));
        let hit = cache.get(&key).unwrap();
        assert_eq!(hit.message, "cached result");
    }

    #[test]
    fn cache_key_canonical_order() {
        // Same params, different key order → same cache key
        let k1 = CacheKey::new("s", "t", &serde_json::json!({"b": 2, "a": 1}));
        let k2 = CacheKey::new("s", "t", &serde_json::json!({"a": 1, "b": 2}));
        assert_eq!(k1, k2);
    }
}
