### dev csearch

Pragmatic search across code using the code map (for symbols/imports) and ripgrep or a Python fallback for text queries.

Use cases:
- Quickly surface definitions by symbol
- Search for package imports
- Wide text searches with optional path/lang filters

Examples:
```bash
# Symbols
./gpt5/devtools/dev csearch --kind symbol --query build_parser

# Text search, limited to TypeScript files in src/
./gpt5/devtools/dev csearch --kind text --query useEffect --lang ts --path-prefix src/

# Import search
./gpt5/devtools/dev csearch --kind import --query requests
```

Flags:
- --lang: repeatable; filters by detected language
- --path-prefix: repeatable; restricts to given prefixes
- --map/--root: override defaults for the code map and repo root
