### dev triage

Create a triage template and optionally open a task in the local task manager.

- new: creates `.triage/<name>/README.md` with a structured checklist
- to-tasks: opens a single task via the task-manager if available

Examples:
```bash
./gpt5/devtools/dev triage new login-bug
./gpt5/devtools/dev triage to-tasks --title "Investigate login failures" --description "See .triage/login-bug" --assignee you --priority 2
```
