### dev preflight

One command that runs a set of local guardrails before opening a PR.

What it does:
- Runs `dev doctor --json` and checks that the environment is OK
- Runs Python unit tests: `python3 -m unittest discover -v`
- Builds a code map for the repository
- Computes change impact (`dev impact`) and prints its output
- Optionally runs an E2E smoke spec if `--e2e <name>` is provided and present

Examples:
```bash
./gpt5/devtools/dev preflight
./gpt5/devtools/dev preflight --e2e smoke
# Fast, skip heavy parts
./gpt5/devtools/dev preflight --quick
```

Output:
- A concise summary block at the end with OK/FAIL per step
- Exits non-zero if any required step fails

Extending:
- You can wire additional checks (lint, type-checkers) into this command in a project-specific fork.
