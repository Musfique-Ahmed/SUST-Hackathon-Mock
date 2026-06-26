---
name: run-tests
description: Auto-detect project type and run tests, reporting pass/fail summary with failure details
allowed-tools:
  - Bash(npm:*)
  - Bash(npx:*)
  - Bash(yarn:*)
  - Bash(pnpm:*)
  - Bash(node:*)
  - Bash(pip:*)
  - Bash(pip3:*)
  - Bash(python:*)
  - Bash(python3:*)
  - Bash(pytest:*)
  - Bash(go:*)
  - Bash(cargo:*)
  - Bash(ruby:*)
  - Bash(bundle:*)
  - Bash(mvn:*)
  - Bash(gradle:*)
  - Bash(ls:*)
  - Bash(test:*)
  - Bash(cat:*)
  - Read
  - Glob
  - Grep
when_to_use: Use when the user wants to run tests in a project and get a summary of results. Examples: 'run tests', 'run the tests', 'test this project', 'are tests passing?', 'run jest', 'run pytest'.
argument-hint: "[optional-pattern]"
arguments:
  - pattern
context: fork
---

# Run Tests

Auto-detect the project type by inspecting existing files, install dependencies if needed, and run the appropriate test command. Reports a summary of results with details for any failing tests.

## Inputs
- `$pattern` (optional): A file path or pattern to scope the test run (e.g., a specific test file or substring to match). If omitted, runs the entire test suite.

## Goal
Run the project's tests and return a concise summary (total/passed/failed counts) plus actionable details for any failures. Do not modify source code; only report.

## Steps

### 1. Detect project type
Inspect the current working directory (or the directory containing `$pattern` if provided) for marker files:

- `package.json` -> Node.js (read `scripts.test` and lockfile to pick npm/yarn/pnpm)
- `pyproject.toml`, `setup.py`, `requirements.txt`, `Pipfile` -> Python (prefer `pytest`, fall back to `unittest`)
- `go.mod` -> Go (`go test ./...`)
- `Cargo.toml` -> Rust (`cargo test`)
- `Gemfile` -> Ruby (`bundle exec rspec` or `rake test`)
- `pom.xml` -> Maven (`mvn test`)
- `build.gradle` / `build.gradle.kts` -> Gradle (`gradle test`)

If multiple ecosystems coexist, prefer the most specific (e.g., `pyproject.toml` over `requirements.txt`). If none detected, report that and stop.

**Success criteria**: A single project type and the exact test command to invoke are identified and logged.

### 2. Ensure dependencies are installed
Check whether dependencies appear already installed:

- Node.js: `node_modules/` exists AND matches the lockfile (`package-lock.json` / `yarn.lock` / `pnpm-lock.yaml`)
- Python: `.venv/` or `venv/` exists, or the required packages import successfully

If dependencies are missing or out of date, run the appropriate install command (`npm install`, `yarn install`, `pnpm install`, `pip install -r requirements.txt`, `pip install -e .`, `go mod download`, `cargo build`, `bundle install`).

**Success criteria**: Install command completes without error, OR existing install is verified intact.

### 3. Execute the tests
Run the detected test command. If `$pattern` was provided, pass it through using the project's native filtering mechanism (e.g., `npm test -- <pattern>`, `pytest <pattern>`, `go test -run <pattern>`).

Capture stdout AND stderr. Set a reasonable timeout (default 10 minutes) but allow override via environment if needed.

**Success criteria**: Test process exits (whether 0 or non-zero) and output is captured for analysis.

### 4. Summarize results
Parse the captured output to extract:

- Total tests run
- Passed count
- Failed count
- Skipped/pending count (if reported)

For each failure, extract:
- Test name / description
- File path and line number (when available)
- The actual error message (first 5 lines max per failure)

Produce a final report in this structure:

```
## Test Summary
- Project type: <detected>
- Test command: <command>
- Result: <PASSED | FAILED>
- Total: N | Passed: N | Failed: N | Skipped: N

## Failures (if any)
### <test name>
- File: <path>:<line>
- Error: <message excerpt>
```

**Success criteria**: Report includes the counts AND, if there were failures, each failure has at minimum a name and an error excerpt. Report is concise (under ~500 lines for large suites).

## Rules

- NEVER modify source code, configs, or test files. This skill is read-and-execute only.
- If a previous run produced lockfiles or caches, do not delete them.
- If install fails, report the install error and stop -- do NOT attempt to run tests against a broken install.
- If tests time out, report which phase (install vs. test) and how long elapsed; do not silently retry.
- If `$pattern` matches no test files in the detected framework, report that clearly rather than running the full suite silently.