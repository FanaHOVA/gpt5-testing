# Task Manager for Parallel AI Agents

A Unix-style CLI tool for managing tasks across multiple AI agent instances working in different git worktrees.

## Features

- Create tasks and subtasks with dependencies
- Block tasks until dependencies are complete
- Add quick notes and improvements with file references
- Update task status and check for conflicts
- Designed for concurrent access across multiple worktrees
- Git-aware with worktree detection
- Rich terminal output with tables and trees

## Installation

```bash
cd task-manager
pip3 install -e .

# The tm command will be installed in your Python bin directory
# You can also use the included wrapper script:
chmod +x tm
./tm --help

# Or add to PATH for global access:
export PATH="$PATH:$(pwd)"
```

## Quick Start

```bash
# Create your first task
tm create "Implement user authentication" --priority high

# Create a dependent task
tm create "Add login endpoint" --depends-on 1 --assignee agent-2

# View all tasks
tm list

# See blocked tasks
tm blocked

# Complete a task and check for conflicts
tm complete 1
```

## Usage

### Task Management

```bash
# Create tasks
tm create "Task title" [options]
  --description, -d     Task description
  --priority, -p        Priority: low, medium, high
  --assignee, -a        Assign to agent (use 'me' for self)
  --depends-on, -D      Task IDs this depends on (multiple)
  --parent              Parent task ID for subtasks
  --files, -f           Files this task affects (multiple)

# List tasks
tm list [options]
  --status, -s          Filter: pending, in-progress, completed, cancelled
  --assignee, -a        Filter by assignee ('me' for self)
  --worktree, -w        Filter by git worktree
  --tree, -t            Show as tree view

# Update tasks
tm update TASK_ID [options]
  --status, -s          Change status
  --assignee, -a        Reassign task
  --priority, -p        Change priority
  --add-files, -f       Add affected files

# Complete tasks
tm complete TASK_ID    # Marks complete and checks for conflicts
```

### Dependencies

```bash
# Add dependencies
tm depend TASK_ID DEPENDS_ON_ID [MORE_IDS...]

# View dependencies
tm deps TASK_ID        # Show dependency graph
tm blocked             # List all blocked tasks
```

### Notes and Documentation

```bash
# Add notes
tm note "Note content" [options]
  --task, -t           Attach to specific task
  --file, -f           File reference (e.g., src/api.py:45)

# View notes
tm notes [options]
  --limit, -n          Number of notes to show
  --task, -t           Filter by task ID
```

### Task Details and Conflicts

```bash
# Show task details
tm show TASK_ID

# Check for conflicts
tm check TASK_ID       # Check if task affects others
```

### Export/Import

```bash
# Export all tasks
tm export tasks_backup.json
```

## Advanced Features

### Environment Variables

```bash
# Set agent ID (defaults to user@hostname)
export TM_AGENT_ID="agent-main"
```

### File References

File references support multiple formats:
- `path/to/file.py` - Just the file
- `path/to/file.py:42` - File with line number
- `path/to/file.py:42-50` - File with line range
- `path/to/file.py#L42` - GitHub-style reference

### Parallel Agent Workflow

1. **Main agent creates tasks:**
   ```bash
   tm create "Implement feature X" --priority high
   tm create "Design API" --parent 1 --assignee agent-design
   tm create "Implement backend" --parent 1 --depends-on 2 --assignee agent-backend
   tm create "Write tests" --parent 1 --depends-on 3 --assignee agent-test
   ```

2. **Agents check their tasks:**
   ```bash
   tm list --assignee me
   tm blocked  # See what's blocking progress
   ```

3. **Update progress:**
   ```bash
   tm update 2 --status in-progress
   tm note "API schema defined in docs/api.yaml" --task 2
   tm complete 2
   ```

4. **Handle conflicts:**
   ```bash
   # After completing a task, check for impacts
   tm check 2
   # Other agents see notifications about affected tasks
   ```

### Task States

- **pending**: Not started yet
- **in-progress**: Currently being worked on
- **completed**: Successfully finished
- **cancelled**: No longer needed

### Database Location

Tasks are stored in `~/.task-manager/tasks.db` by default. This allows all agents across different worktrees to share the same task database.

## Examples

See `examples.sh` for comprehensive usage examples.

## Architecture

- **Storage**: SQLite with file locking for concurrent access
- **CLI**: Python Click framework for Unix-style interface
- **Display**: Rich library for beautiful terminal output
- **Concurrency**: File-based locking prevents conflicts
- **Git Integration**: Automatic worktree detection