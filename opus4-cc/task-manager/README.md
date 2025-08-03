# Task Manager for Parallel AI Agents

A Unix-style CLI tool designed for AI agents working in parallel across different git worktrees. This tool provides synchronized task management with dependency tracking, notifications, and impact analysis.

## Features

- **Parallel Agent Support**: Tasks are stored in a shared location accessible across all git worktrees
- **Dependency Management**: Tasks can depend on other tasks and are automatically blocked/unblocked
- **File Reference Tracking**: Track which files are related to each task
- **Impact Analysis**: When tasks complete, analyze potential impacts on other tasks
- **Notification System**: Get notified when blocked tasks become available
- **Unix-style CLI**: Designed to feel like a native Unix utility

## Installation

The task manager is a standalone Python script. To use it system-wide:

```bash
# Add to your PATH (e.g., in ~/.bashrc or ~/.zshrc)
export PATH="/path/to/task-manager:$PATH"

# Or create a symlink
ln -s /path/to/task-manager/tm /usr/local/bin/tm
```

## Usage

### Adding Tasks

```bash
# Basic task
tm add "Implement user authentication"

# Task with details
tm add "Refactor database module" \
  -d "Split monolithic module into smaller components" \
  -p high \
  -f src/database.py src/models.py

# Subtask with dependencies
tm add "Add OAuth support" \
  --parent 1 \
  --depends-on 2 3 \
  -a agent-2
```

### Listing Tasks

```bash
# List all tasks
tm list

# List with details
tm list -v

# Filter by status
tm list -s pending
tm list -s blocked

# Filter by assignee
tm list -a agent-1
```

### Working on Tasks

```bash
# Start working on a task
tm start 5

# Update task details
tm update 5 -s in_progress -p critical

# Complete a task (triggers dependency checks)
tm complete 5
```

### Checking Notifications

```bash
# Check your notifications
tm notifications

# Check notifications for specific agent
tm notifications -a agent-2
```

### Task Details

```bash
# Show detailed information about a task
tm show 5
```

## Task States

- **pending**: Task is ready to be worked on
- **in_progress**: Task is currently being worked on
- **completed**: Task has been finished
- **blocked**: Task is waiting for dependencies
- **cancelled**: Task has been cancelled

## Priority Levels

- **low** (○): Low priority tasks
- **medium** (◐): Default priority
- **high** (●): High priority tasks
- **critical** (⚠): Critical tasks requiring immediate attention

## Example Workflow

### Scenario 1: Breaking Down a Large Feature

```bash
# Main task
tm add "Implement real-time chat feature" -p high

# Subtasks
tm add "Design WebSocket protocol" --parent 1 -a agent-1
tm add "Implement server-side handlers" --parent 1 --depends-on 2 -a agent-2
tm add "Create frontend components" --parent 1 --depends-on 2 -a agent-3
tm add "Add message persistence" --parent 1 --depends-on 3 -a agent-2
```

### Scenario 2: Tracking Technical Debt

```bash
# While working on a feature, notice an improvement opportunity
tm add "Refactor authentication middleware" \
  -d "Current implementation has duplicate code between OAuth and JWT handlers" \
  -f src/middleware/auth.py \
  -p low
```

### Scenario 3: Handling Blocked Tasks

```bash
# Agent 1 completes the API design
tm complete 2

# Agent 2 automatically gets notified that task 3 is now unblocked
tm notifications -a agent-2
# Output: Task 3 is now unblocked
```

## Data Storage

Tasks are stored in `~/.task-manager/tasks.json`, making them accessible across all git worktrees. The data includes:

- Task metadata (id, title, description, dates)
- Status and priority information
- Dependencies and relationships
- File references
- Assignee and worktree information

## Best Practices

1. **Use descriptive titles**: Make it clear what the task accomplishes
2. **Add file references**: Help future agents understand context
3. **Set appropriate priorities**: Critical > High > Medium > Low
4. **Assign tasks thoughtfully**: Consider agent workload and expertise
5. **Complete tasks promptly**: Unblock dependent tasks as soon as possible
6. **Check notifications regularly**: Stay aware of newly available tasks

## Advanced Features

### Impact Analysis

When a task is completed, the system analyzes potential impacts:

- Checks if completed task modified files referenced by other tasks
- Generates warnings for tasks that might need review
- Stores notifications for affected assignees

### Dependency Chains

Tasks can have complex dependency relationships:

```bash
# Task 5 depends on both 3 and 4
tm add "Deploy to production" --depends-on 3 4

# Task 6 depends on 5, creating a chain
tm add "Post-deployment validation" --depends-on 5
```

## Troubleshooting

### Task Not Found
Ensure you're using the correct task ID. Use `tm list` to see all tasks.

### Notifications Not Appearing
Check that your USER environment variable is set correctly, or specify assignee explicitly.

### Permission Issues
Ensure `~/.task-manager` directory has appropriate permissions for all agents.

## Future Enhancements

Potential improvements for the task manager:

1. Task templates for common workflows
2. Bulk operations for managing multiple tasks
3. Task archiving for completed tasks
4. Integration with git hooks
5. Task estimation and time tracking
6. Priority-based task suggestions