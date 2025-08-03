### gpt5/task-manager

A minimal, dependency-free, local task manager for coordinating parallel AI agents (and humans). It stores tasks, dependencies, notes, resources, and an append-only event log in a single SQLite database.

- **Binary/Entrypoint**: `gpt5/task-manager/tm`
- **Library**: `gpt5/task-manager/cli.py` and `gpt5/task-manager/db.py`
- **Backend**: SQLite with WAL enabled

### Features
- **Tasks**: title, description, status, assignee, priority, due date, timestamps
- **Statuses**: `pending`, `in_progress`, `blocked`, `completed`, `cancelled`
- **Dependencies**: graph of `task -> depends_on_task`
- **Notes**: freeform text notes with optional file reference
- **Resources**: annotate tasks with impacted resources to enable impact analysis
- **Events**: append-only stream for all changes; supports `watch` streaming
- **Doctor**: cycle detection and auto-unblock for resolved blockers

### Installation
- No external Python dependencies; uses stdlib only.
- Python 3.8+ recommended.

Option 1: Run via the repo path

```bash
# Make the script executable (once)
chmod +x gpt5/task-manager/tm

# Use it directly
./gpt5/task-manager/tm --help
```

Option 2: Put it on your PATH

```bash
# from repo root
ln -sf "$PWD/gpt5/task-manager/tm" /usr/local/bin/tm  # or another directory in $PATH

tm --help
```

### Configuration
- **TM_DB_DIR**: directory for the SQLite DB (default: `~/.gpt5`)
- **TM_DB**: full DB path (default: `~/.gpt5/tasks.db`)
- **TM_ACTOR**: actor name for events; falls back to `$USER`/`$USERNAME`
- **TM_ASSIGNEE**: used by `--me` filters

### Data model (SQLite)
- **tables**: `tasks`, `dependencies`, `notes`, `resources`, `events`
- **indexes**: created for common queries (status, assignee, resource, event timestamps)
- **journal mode**: WAL; `busy_timeout` enabled for simple concurrent access

### Resources model
Resources annotate what a task touches or expects.
- **Kinds**: `touch`, `adds`, `removes`, `modifies`, `depends`
- **Format**: `KIND:VALUE`
  - Examples: `touch:file:path/to/file`, `modifies:endpoint:GET /api/foo`, `removes:feature:legacy-mode`

Impact rules when a task is completed:
- **removes**: emits `impact_conflict` for any other task that `touch|adds|modifies|depends` on the same resource
- **modifies**: emits `impact_notice` for tasks that `depends|touch|modifies` the same resource
- **adds**: emits `impact_notice` for tasks that `depends` on the resource

### Quick start
```bash
# 1) Initialize the database
./gpt5/task-manager/tm init

# 2) Create a task
./gpt5/task-manager/tm add "Implement auth" -d "Add login + signup" -a alice -p 2 --due [DATE REDACTED] \
  --resource modifies:endpoint:POST /api/login --link app/server/auth.py

# 3) List tasks
./gpt5/task-manager/tm list --me   # or: --status in_progress

# 4) Show details
./gpt5/task-manager/tm show 1

# 5) Add dependency and attempt start
./gpt5/task-manager/tm depend 1 --on 2
./gpt5/task-manager/tm start 1     # auto-blocks if unmet deps

# 6) Complete a task
./gpt5/task-manager/tm complete 2 -m "Merged PR #123"

# 7) Watch events
./gpt5/task-manager/tm watch --follow --me
```

### CLI reference
Run `tm --help` or `tm <subcmd> --help` for details. Summary:
- **init**: initialize the database
- **add**: create a task; options include `--description`, `--assignee`, `--priority`, `--due`, `--depends`, `--link`, `--resource`
- **list**: filter by `--status`, `--assignee`, or `--me`
- **show <id>**: show details, dependencies, resources, and notes
- **update <id>**: update fields `--title`, `--description`, `--assignee`, `--priority`, `--due`
- **status <id> <status>**: set status
- **start <id>**: set `in_progress` if deps met, else mark `blocked`
- **block <id> [--reason]** / **unblock <id>**
- **complete <id> [-m msg]**: mark complete and run impact checks
- **depend <id> --on <depId>** / **undepend <id> --on <depId>**
- **assign <id> -a <assignee>**
- **note <id> <text> [--file path]**
- **link <id> <file>**: shorthand for `resource touch:file:<file>`
- **resource <id> <KIND:VALUE>...**
- **watch [--since N] [--follow] [--interval S] [--assignee X | --me]**
- **doctor**: cycle detection + auto-unblock

### Concurrency notes
- SQLite WAL and `busy_timeout` are enabled.
- Event log is append-only; consumers can safely tail via `watch`.

### Development
- Entrypoint script: `gpt5/task-manager/tm` calls `cli.main()` and ensures the script directory is importable.
- Code style: straightforward stdlib Python; no external deps.

### Troubleshooting
- If you see "Task N not found", ensure you initialized the DB and are pointing to the correct `--db` or `TM_DB` path.
- Use `watch --since <id>` to resume event streaming from a known event.
- Run `doctor` if tasks are stuck in `blocked`.
