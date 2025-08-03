### gpt5/devtools

Developer utilities for local productivity:
- `doctor`: environment checks for core tools
- `bootstrap`: one-command setup and smoke test
- `code-map`: simple repository index with build/find subcommands
- `csearch`: symbol/import/text search with filters
- `tasks-graph`: output Mermaid graph from task DB
- `impact`: show tasks linked to changed files
- `seed`: populate task-manager DB with sample tasks
- `repro scaffold`: create a vcrpy-ready repro under .repro/
- `e2e`: scaffold and run lightweight E2E specs
- `preflight`: run doctor, tests, code-map, impact, and optional E2E
- `preflight-smol`: repo-specific preflight for smol-podcaster (API health, Celery ping, optional deps install)
- `broker`: manage a local RabbitMQ via Docker (rabbitmq:3-management)
- `flake`: rerun suites multiple times to detect flaky tests
- `codemod`: regex-based preview/apply with safety rails
- `triage`: create triage templates and open tasks
- `trace`: cProfile-based expression profiler
- `runbook`: generate runbook Markdown from task DB

Usage:

```bash
./gpt5/devtools/dev doctor --json
./gpt5/devtools/dev bootstrap
./gpt5/devtools/dev code-map build --root .
./gpt5/devtools/dev code-map find --kind symbol --query build_parser
./gpt5/devtools/dev csearch --kind text --query TODO --path-prefix gpt5/
./gpt5/devtools/dev tasks-graph --format mermaid
./gpt5/devtools/dev impact --ref origin/main
./gpt5/devtools/dev seed --count 8
./gpt5/devtools/dev repro scaffold login-bug --url https://httpbin.org/get
./gpt5/devtools/dev e2e scaffold smoke --url https://example.com
./gpt5/devtools/dev preflight --e2e smoke
./gpt5/devtools/dev preflight-smol --install --quick
./gpt5/devtools/dev broker up
./gpt5/devtools/dev broker logs --tail 100
./gpt5/devtools/dev broker down
./gpt5/devtools/dev flake --start devtools/testdata/flake_ok --pattern 'test_*.py' --runs 2
./gpt5/devtools/dev codemod plan --root . --regex 'foo' --replace 'bar'
./gpt5/devtools/dev triage new login-bug
./gpt5/devtools/dev trace run --expr "sum(range(100000))" --out /tmp/trace.prof
./gpt5/devtools/dev runbook generate --task 1
```

See docs:
- docs/doctor_bootstrap.md
- docs/code_map.md
- docs/csearch.md
- docs/tasks_graph.md
- docs/impact.md
- docs/seed.md
- docs/repro.md
- docs/e2e.md
- docs/preflight.md
- docs/flake.md
- docs/codemod.md
- docs/triage.md
- docs/trace.md
- docs/runbook.md
