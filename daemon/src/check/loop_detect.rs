use std::time::{Duration, Instant};

/// Check if a tool key has been invoked too many times within a time window.
/// Returns a warning message if the threshold is reached.
pub fn check_loop(
    history: &[(String, Instant)],
    tool_key: &str,
    window_secs: u64,
    threshold: u32,
) -> Option<String> {
    let cutoff = Instant::now() - Duration::from_secs(window_secs);
    let count = history
        .iter()
        .filter(|(k, t)| k == tool_key && *t > cutoff)
        .count();
    if count >= threshold as usize {
        Some(format!(
            "'{}' invoked {} times in {}s — possible retry loop",
            tool_key, count, window_secs
        ))
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn under_threshold_returns_none() {
        let now = Instant::now();
        let history: Vec<(String, Instant)> = (0..3)
            .map(|_| ("git".to_string(), now))
            .collect();
        assert!(check_loop(&history, "git", 120, 5).is_none());
    }

    #[test]
    fn at_threshold_returns_warning() {
        let now = Instant::now();
        let history: Vec<(String, Instant)> = (0..5)
            .map(|_| ("git".to_string(), now))
            .collect();
        let result = check_loop(&history, "git", 120, 5);
        assert!(result.is_some());
        assert!(result.unwrap().contains("possible retry loop"));
    }

    #[test]
    fn different_keys_dont_cross_count() {
        let now = Instant::now();
        let mut history: Vec<(String, Instant)> = (0..3)
            .map(|_| ("git".to_string(), now))
            .collect();
        history.extend((0..3).map(|_| ("npm".to_string(), now)));
        assert!(check_loop(&history, "git", 120, 5).is_none());
        assert!(check_loop(&history, "npm", 120, 5).is_none());
    }

    #[test]
    fn expired_entries_not_counted() {
        let old = Instant::now() - Duration::from_secs(300);
        let now = Instant::now();
        let mut history: Vec<(String, Instant)> = (0..4)
            .map(|_| ("git".to_string(), old))
            .collect();
        history.push(("git".to_string(), now));
        assert!(check_loop(&history, "git", 120, 5).is_none());
    }
}
