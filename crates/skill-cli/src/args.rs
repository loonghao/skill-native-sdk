//! CLI argument definitions — clap derive API.

use clap::{Parser, Subcommand, ValueEnum};

pub const DEFAULT_SKILLS_DIR: &str = "./skills";

#[derive(Parser)]
#[command(
    name = "skill",
    about = "skill-native-sdk CLI — SKILL.md → anywhere",
    version
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,
}

/// Output format for `run` and `chain` subcommands.
#[derive(Debug, Clone, ValueEnum)]
pub enum OutputFormat {
    /// Full JSON (default for `run`)
    Json,
    /// Minimal token format — ~3-5× smaller (default for `chain`)
    Toon,
    /// MCP tool_result wire format
    Mcp,
}

impl std::fmt::Display for OutputFormat {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            OutputFormat::Json => write!(f, "json"),
            OutputFormat::Toon => write!(f, "toon"),
            OutputFormat::Mcp  => write!(f, "mcp"),
        }
    }
}

#[derive(Subcommand)]
pub enum Commands {
    /// List all available skills
    List {
        /// Skills root directory
        #[arg(long, short = 'd', default_value = DEFAULT_SKILLS_DIR)]
        skills_dir: String,
        /// Filter by domain (e.g. maya, finance)
        #[arg(long)]
        domain: Option<String>,
    },

    /// Show detailed information about a skill and its tools
    Describe {
        /// Skill name
        skill_name: String,
        #[arg(long, short = 'd', default_value = DEFAULT_SKILLS_DIR)]
        skills_dir: String,
    },

    /// Print the CapabilityGraph for a skill as JSON
    Graph {
        /// Skill name
        skill_name: String,
        #[arg(long, short = 'd', default_value = DEFAULT_SKILLS_DIR)]
        skills_dir: String,
    },

    /// Execute a single skill tool
    Run {
        /// Skill name
        skill_name: String,
        /// Tool name
        tool_name: String,
        /// Input parameters as a JSON object string
        #[arg(long, short = 'p')]
        params: Option<String>,
        /// Output format
        #[arg(long, short = 'o', default_value = "json")]
        output: OutputFormat,
        #[arg(long, short = 'd', default_value = DEFAULT_SKILLS_DIR)]
        skills_dir: String,
    },

    /// Execute a tool and optionally follow the on_success chain
    Chain {
        /// Skill name
        skill_name: String,
        /// Entry tool name
        #[arg(long, required = true)]
        entry: String,
        /// Parameters for the entry tool (JSON object string)
        #[arg(long, short = 'p')]
        params: Option<String>,
        /// Automatically follow on_success hints
        #[arg(long)]
        follow_success: bool,
        /// Output format
        #[arg(long, short = 'o', default_value = "toon")]
        output: OutputFormat,
        #[arg(long, short = 'd', default_value = DEFAULT_SKILLS_DIR)]
        skills_dir: String,
    },
}
