### dev flake

Detect flaky tests by repeatedly running a test suite with different seeds.

- Strategy: rerun unittest discovery multiple times while varying PYTHONHASHSEED
- Output: summary and optional JSON per-run results

Examples:
```bash
# Run 5 times on default test discovery in CWD
./gpt5/devtools/dev flake --runs 5

# Run against a directory and pattern
./gpt5/devtools/dev flake --start devtools/testdata/flake_ok --pattern 'test_*.py' --runs 3 --seed 100
```

Interpretation:
- Non-zero exit if any run fails; inspect JSON or stdout to identify failing runs
- Use with CI to quarantine flaky suites and file a follow-up task automatically
