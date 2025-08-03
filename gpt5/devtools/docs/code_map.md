### dev code-map

Build and query a lightweight repository index. Extracts symbols and imports for common languages.

- Output: JSON at ~/.gpt5/code_map.json by default
- Languages: Python, TS/JS (basic), Go (basic), Ruby (basic)
- Skips dotfiles and hidden directories.

Examples:

```bash
# Build map for repo
./gpt5/devtools/dev code-map build --root .

# Find by symbol
./gpt5/devtools/dev code-map find --kind symbol --query build_parser

# Find by import package
./gpt5/devtools/dev code-map find --kind import --query requests

# Find by path fragment
./gpt5/devtools/dev code-map find --kind path --query task-manager/cli.py
```

Notes:
- Heuristics are intentionally simple and dependency-free; extend parsers per-language as needed.
- Pairs with `dev csearch` for content search and `dev impact` for change mapping.
