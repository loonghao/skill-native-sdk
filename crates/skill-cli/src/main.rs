//! skn — skill-native CLI binary entry point.

use std::process;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let code = skill_cli::run_cli(&args);
    process::exit(code);
}
