### dev codemod

Safe, dependency-free codemod with preview + apply.

- plan: preview unified diffs for regex replacement across selected files
- apply: write the changes (requires --yes)

Selectors:
- --root: repo subtree to scan (defaults to CWD)
- --lang: filter by detected language (repeatable)
- --path-prefix: filter by path prefix (repeatable)

Examples:
```bash
# Preview replacing foo->bar in Python files under src/
./gpt5/devtools/dev codemod plan --root src --lang python --regex 'foo' --replace 'bar'

# Apply to the first 100 matches across TS/JS files
./gpt5/devtools/dev codemod apply --root web --lang ts --lang js --regex 'OldAPI' --replace 'NewAPI' --limit 100 --yes
```

Notes:
- Uses simple regex with MULTILINE flag; extend as needed for AST-aware edits.
- Recommended: run `dev preflight` after applying a codemod.
