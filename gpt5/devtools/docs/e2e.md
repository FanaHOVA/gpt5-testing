### dev e2e

Scaffold and run lightweight E2E specs.

- `scaffold`: creates `.e2e/<name>/spec.py` with a Playwright-based test if available; otherwise a stub that still runs.
- `run`: executes the spec via Python.

Examples:
```bash
# Create a spec
./gpt5/devtools/dev e2e scaffold smoke --url https://example.com

# Run it
python3 .e2e/smoke/spec.py
# or
./gpt5/devtools/dev e2e run smoke
```

Notes:
- Optional: `pip install playwright` and `playwright install` to enable real browser automation.
- The stub path enables use without browser dependencies.
