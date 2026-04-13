//! Zero-dep ANSI colour helpers.
//!
//! Respects `NO_COLOR` env-var and non-tty stdout (exactly like the old Python shim).

use std::io::IsTerminal as _;

static USE_COLOR: std::sync::OnceLock<bool> = std::sync::OnceLock::new();

pub fn use_color() -> bool {
    *USE_COLOR.get_or_init(|| {
        std::io::stdout().is_terminal() && std::env::var("NO_COLOR").is_err()
    })
}

macro_rules! ansi {
    ($code:expr, $text:expr) => {
        if use_color() {
            format!("\x1b[{}m{}\x1b[0m", $code, $text)
        } else {
            $text.to_string()
        }
    };
}

pub fn bold(s: &str) -> String   { ansi!("1",  s) }
pub fn dim(s: &str) -> String    { ansi!("2",  s) }
pub fn cyan(s: &str) -> String   { ansi!("36", s) }
pub fn green(s: &str) -> String  { ansi!("32", s) }
pub fn yellow(s: &str) -> String { ansi!("33", s) }
pub fn red(s: &str) -> String    { ansi!("31", s) }
pub fn magenta(s: &str) -> String { ansi!("35", s) }
