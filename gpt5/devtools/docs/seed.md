### dev seed

Populate the local task-manager DB with deterministic sample tasks and a simple dependency chain. Useful for demos and smoke tests.

Examples:
```bash
./gpt5/devtools/dev seed --count 10
./gpt5/devtools/dev seed --db /tmp/tasks.db --count 5 --force
```

Notes:
- Defaults to `~/.gpt5/tasks.db`
- Will refuse to seed a non-empty DB unless `--force` is provided
