### dev runbook

Generate a runbook Markdown file from a task in the local task-manager DB.

Examples:
```bash
./gpt5/devtools/dev runbook generate --task 1
# or with a specific DB and output path
./gpt5/devtools/dev runbook generate --task 1 --db /tmp/tasks.db --out /tmp/runbook.md
```

The runbook includes:
- Task metadata (status, assignee, priority, due)
- Description
- Resources (from the resources table)
- Notes (from the notes table)
