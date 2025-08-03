### dev doctor & bootstrap

Doctor performs environment checks and prints JSON or human-readable results with hints.

Checks:
- python, git, node, npm, rg (ripgrep), ctags (universal-ctags), sqlite3

Bootstrap:
- Runs doctor (must pass), initializes the task-manager DB, adds a smoke task, prints details.

Examples:
```bash
./gpt5/devtools/dev doctor --json | jq .ok
./gpt5/devtools/dev bootstrap
```

Tips:
- On macOS, prefer universal-ctags: `brew install --HEAD universal-ctags`.
- Set `DEV_ROOT` and `DEV_CACHE` to control root and cache locations.
