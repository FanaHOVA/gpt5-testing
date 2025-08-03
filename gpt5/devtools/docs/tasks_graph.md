### dev tasks-graph

Emit a dependency graph from the task-manager SQLite DB.

- Formats: Mermaid (default), edges list
- Input DB: ~/.gpt5/tasks.db by default, or pass --db

Examples:
```bash
./gpt5/devtools/dev tasks-graph --format mermaid > graph.mmd
```

Paste the output into a Mermaid renderer to visualize the critical path and cycles (use task-manager `doctor` to flag cycles).
