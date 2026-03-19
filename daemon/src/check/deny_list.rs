/// Glob-based file deny list — blocks writes to sensitive files.
///
/// Ported from `src/devloop/runtime/deny_list.py`. Matches against the full
/// path, basename, and every suffix of the path parts so that directory-scoped
/// patterns like `.aws/*` catch paths like `home/user/.aws/credentials`.
use glob::Pattern;

/// Pre-compiled deny patterns with optional allow overrides.
pub struct DenyList {
    patterns: Vec<(String, Pattern)>,
    allow_patterns: Vec<Pattern>,
}

pub const BUILTIN_DENY_PATTERNS: &[&str] = &[
    // Environment / dotenv
    ".env",
    ".env.*",
    // Cryptographic keys and certificates
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    // Credentials files (any extension)
    "credentials.*",
    // Anything with "secret" in the name
    "*secret*",
    // Cloud provider credential directories
    ".aws/*",
    ".ssh/*",
    // Token / auth files
    "*.keystore",
    "*.jks",
    ".netrc",
    ".npmrc",
    ".pypirc",
];

impl DenyList {
    /// Build the default deny list from the hardcoded patterns.
    pub fn default_patterns() -> Self {
        Self::compile(BUILTIN_DENY_PATTERNS.iter().map(|s| s.to_string()).collect(), &[])
    }

    /// Build a deny list with config overrides applied.
    ///
    /// - `extra`: additional glob patterns to deny
    /// - `remove`: built-in patterns to remove (exact match on pattern string)
    /// - `allow`: glob patterns that override deny (e.g. `.env.example*`)
    pub fn from_config(extra: &[String], remove: &[String], allow: &[String]) -> Self {
        let mut patterns: Vec<String> = BUILTIN_DENY_PATTERNS
            .iter()
            .map(|s| s.to_string())
            .filter(|p| !remove.contains(p))
            .collect();

        for p in extra {
            if !patterns.contains(p) {
                patterns.push(p.clone());
            }
        }

        Self::compile(patterns, allow)
    }

    fn compile(raw: Vec<String>, allow: &[String]) -> Self {
        let patterns = raw
            .into_iter()
            .filter_map(|p| Pattern::new(&p).ok().map(|compiled| (p, compiled)))
            .collect();

        let allow_patterns = allow
            .iter()
            .filter_map(|p| Pattern::new(p).ok())
            .collect();

        Self { patterns, allow_patterns }
    }

    /// Check if a path matches any allow pattern (overrides deny).
    fn is_allowed(&self, path: &str) -> bool {
        if self.allow_patterns.is_empty() {
            return false;
        }
        let basename = path.rsplit('/').next().unwrap_or(path);
        for pattern in &self.allow_patterns {
            if pattern.matches(path) || pattern.matches(basename) {
                return true;
            }
        }
        false
    }

    /// Check if a file path matches any denied pattern.
    ///
    /// Returns `Some((pattern, reason))` if blocked, `None` if allowed.
    pub fn check(&self, path: &str) -> Option<DenyMatch> {
        // Normalize: strip leading slashes for relative matching
        let path = path.strip_prefix('/').unwrap_or(path);

        // Allow patterns override deny patterns
        if self.is_allowed(path) {
            return None;
        }

        for (raw, pattern) in &self.patterns {
            // Match against the full path
            if pattern.matches(path) {
                return Some(DenyMatch {
                    pattern: raw.clone(),
                });
            }

            // Match against just the filename (basename)
            if let Some(basename) = path.rsplit('/').next() {
                if pattern.matches(basename) {
                    return Some(DenyMatch {
                        pattern: raw.clone(),
                    });
                }
            }

            // Match against each suffix of the path parts so that
            // directory-scoped patterns like ".aws/*" work on paths
            // like "home/user/.aws/credentials"
            let parts: Vec<&str> = path.split('/').collect();
            for i in 1..parts.len() {
                let sub = parts[i..].join("/");
                if pattern.matches(&sub) {
                    return Some(DenyMatch {
                        pattern: raw.clone(),
                    });
                }
            }
        }

        None
    }
}

#[derive(Debug, Clone)]
pub struct DenyMatch {
    pub pattern: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dl() -> DenyList {
        DenyList::default_patterns()
    }

    #[test]
    fn blocks_dotenv() {
        assert!(dl().check(".env").is_some());
        assert!(dl().check(".env.local").is_some());
        assert!(dl().check(".env.production").is_some());
        assert!(dl().check("config/.env").is_some());
    }

    #[test]
    fn blocks_crypto_keys() {
        assert!(dl().check("server.key").is_some());
        assert!(dl().check("certs/ca.pem").is_some());
        assert!(dl().check("auth.p12").is_some());
        assert!(dl().check("store.pfx").is_some());
    }

    #[test]
    fn blocks_credentials() {
        assert!(dl().check("credentials.json").is_some());
        assert!(dl().check("config/credentials.yaml").is_some());
    }

    #[test]
    fn blocks_secrets() {
        assert!(dl().check("secret.txt").is_some());
        assert!(dl().check("my_secret_key").is_some());
        assert!(dl().check("app-secrets.yaml").is_some());
    }

    #[test]
    fn blocks_cloud_dirs() {
        assert!(dl().check(".aws/credentials").is_some());
        assert!(dl().check(".ssh/id_rsa").is_some());
        assert!(dl().check("home/user/.aws/config").is_some());
        assert!(dl().check("/home/user/.ssh/authorized_keys").is_some());
    }

    #[test]
    fn blocks_auth_files() {
        assert!(dl().check("release.keystore").is_some());
        assert!(dl().check("truststore.jks").is_some());
        assert!(dl().check(".netrc").is_some());
        assert!(dl().check(".npmrc").is_some());
        assert!(dl().check(".pypirc").is_some());
    }

    #[test]
    fn from_config_extra_patterns() {
        let dl = DenyList::from_config(&["*.vault".to_string()], &[], &[]);
        assert!(dl.check("secrets.vault").is_some());
        // Built-in still works
        assert!(dl.check(".env").is_some());
    }

    #[test]
    fn from_config_remove_patterns() {
        let dl = DenyList::from_config(&[], &[".npmrc".to_string()], &[]);
        // Removed pattern no longer blocks
        assert!(dl.check(".npmrc").is_none());
        // Other built-ins still work
        assert!(dl.check(".env").is_some());
        assert!(dl.check(".pypirc").is_some());
    }

    #[test]
    fn from_config_extra_and_remove() {
        let dl = DenyList::from_config(
            &["*.vault".to_string()],
            &[".npmrc".to_string(), ".pypirc".to_string()],
            &[],
        );
        assert!(dl.check("secrets.vault").is_some());
        assert!(dl.check(".npmrc").is_none());
        assert!(dl.check(".pypirc").is_none());
        assert!(dl.check(".env").is_some());
    }

    #[test]
    fn from_config_allow_patterns() {
        let dl = DenyList::from_config(&[], &[], &[".env.example*".to_string()]);
        // Allow overrides deny
        assert!(dl.check("docs/.env.example.md").is_none());
        assert!(dl.check(".env.example").is_none());
        // Non-example .env files still blocked
        assert!(dl.check(".env").is_some());
        assert!(dl.check(".env.local").is_some());
        assert!(dl.check(".env.production").is_some());
    }

    #[test]
    fn allows_normal_files() {
        assert!(dl().check("src/main.rs").is_none());
        assert!(dl().check("package.json").is_none());
        assert!(dl().check("README.md").is_none());
        assert!(dl().check("src/config.ts").is_none());
        assert!(dl().check("Cargo.toml").is_none());
        assert!(dl().check(".gitignore").is_none());
    }
}

#[cfg(test)]
mod proptests {
    use super::*;
    use proptest::prelude::*;

    proptest! {
        #[test]
        fn never_panics(path in "\\PC{1,500}") {
            let dl = DenyList::default_patterns();
            let _ = dl.check(&path);
        }

        #[test]
        fn deterministic(path in "\\PC{1,200}") {
            let dl = DenyList::default_patterns();
            let r1 = dl.check(&path);
            let r2 = dl.check(&path);
            prop_assert_eq!(r1.is_some(), r2.is_some());
        }

        #[test]
        fn remove_patterns_always_subtract(
            remove_idx in 0usize..BUILTIN_DENY_PATTERNS.len(),
            path in "\\PC{1,200}"
        ) {
            let removed = BUILTIN_DENY_PATTERNS[remove_idx].to_string();
            let dl_full = DenyList::default_patterns();
            let dl_reduced = DenyList::from_config(&[], &[removed.clone()], &[]);

            let full_result = dl_full.check(&path);
            let reduced_result = dl_reduced.check(&path);

            // If the reduced list allows it, we can't say much.
            // But if the reduced list blocks it, the full list must too.
            if reduced_result.is_some() {
                prop_assert!(full_result.is_some(),
                    "Reduced list blocked but full list allowed: path={}", path);
            }
        }

        #[test]
        fn extra_patterns_only_add_blocks(
            extra in "[a-z*.]{2,20}",
            path in "[a-zA-Z0-9_./\\-]{1,100}"
        ) {
            let dl_base = DenyList::default_patterns();
            let dl_extra = DenyList::from_config(&[extra], &[], &[]);

            let base_result = dl_base.check(&path);
            let extra_result = dl_extra.check(&path);

            // If base blocks, extra must also block (extra only adds)
            if base_result.is_some() {
                prop_assert!(extra_result.is_some(),
                    "Base blocked but extra allowed: path={}", path);
            }
        }
    }
}
