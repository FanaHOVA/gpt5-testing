### dev impact

Show tasks that are likely impacted by your current changes by matching changed file paths against task resources of the form `touch:file:<path>`.

Examples:
```bash
# Compare to origin/main
./gpt5/devtools/dev impact --ref origin/main

# Use current working copy
./gpt5/devtools/dev impact
```

Notes:
- Uses `git` to list changed files. Filters against the task-manager DB’s `resources` table.
- Combine with `tm resource <id> touch:file:<path>` to keep the links current.
