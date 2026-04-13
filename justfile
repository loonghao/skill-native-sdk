# skill-native-sdk development commands
# Usage: just <recipe>  (or: vx just <recipe>)

set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
set shell := ["sh", "-cu"]

default:
    @just --list

# ── Rust ──────────────────────────────────────────────────────────────────────

# Check all Rust crates
check:
    cargo check --workspace

# Run clippy with CI-identical flags
clippy:
    cargo clippy --workspace -- -D warnings

# Format Rust code
fmt:
    cargo fmt --all

# Format check (CI mode)
fmt-check:
    cargo fmt --all -- --check

# Run Rust tests
test-rust:
    cargo test --workspace

# Rust code coverage (requires cargo-tarpaulin, Linux only)
rust-cov:
    cargo tarpaulin --workspace --out Html --out Xml --output-dir coverage/ --timeout 300

# ── Python ────────────────────────────────────────────────────────────────────

# Build and install the extension in dev mode
[unix]
dev:
    #!/usr/bin/env sh
    set -eu
    if [ -z "${VIRTUAL_ENV:-}" ] && [ -z "${CONDA_PREFIX:-}" ] && [ -z "${CI:-}" ]; then \
        if [ ! -d .venv ]; then python -m venv .venv; fi; \
        . .venv/bin/activate; \
    fi
    pip install maturin 2>/dev/null || true
    maturin develop --features python-bindings,ext-module

[windows]
dev:
    if (-not $env:VIRTUAL_ENV -and -not $env:CONDA_PREFIX -and -not $env:CI) { \
        if (-not (Test-Path .venv)) { python -m venv .venv }; \
        & .\.venv\Scripts\Activate.ps1; \
    }
    pip install maturin -q 2>$null
    maturin develop --features python-bindings,ext-module

# Build ABI3 wheel + pip install (CI-friendly, no virtualenv required)
install:
    maturin build --release --out dist --features python-bindings,ext-module,abi3-py310
    pip install --force-reinstall --no-index --find-links dist skill-native-sdk

# Run Python tests (requires `just dev` or `just install` first)
test:
    pytest tests/ -v --tb=short

# Run Python tests with coverage
test-cov:
    pytest tests/ -v --cov=skill_native_sdk --cov-report=term --cov-report=xml:coverage.xml

# Lint Python code
lint-py:
    ruff check python/skill_native_sdk/ tests/

# Fix Python lint issues
lint-py-fix:
    ruff check --fix python/skill_native_sdk/ tests/
    ruff format python/skill_native_sdk/ tests/

# ── Unified (CI + local) ──────────────────────────────────────────────────────

# Lint all (Rust + Python) — same checks as CI
lint: clippy fmt-check lint-py

# Fix all lint issues
lint-fix: fmt lint-py-fix

# Pre-flight check — run before committing (same as CI rust-check job)
preflight: check clippy fmt-check test-rust

# Full CI pipeline (Rust + Python)
ci: preflight install test lint-py

# Build release wheels (ABI3)
build:
    maturin build --release --features python-bindings,ext-module,abi3-py310

# ── Docs ──────────────────────────────────────────────────────────────────────

# Generate Rust API docs
doc:
    cargo doc --workspace --no-deps --open

# ── Clean ─────────────────────────────────────────────────────────────────────

[unix]
clean:
    rm -rf dist build target .coverage coverage.xml htmlcov/

[windows]
clean:
    if (Test-Path dist)     { Remove-Item -Recurse -Force dist }
    if (Test-Path build)    { Remove-Item -Recurse -Force build }
    if (Test-Path target)   { Remove-Item -Recurse -Force target }
    if (Test-Path htmlcov)  { Remove-Item -Recurse -Force htmlcov }
    Remove-Item -ErrorAction SilentlyContinue -Force .coverage, coverage.xml
