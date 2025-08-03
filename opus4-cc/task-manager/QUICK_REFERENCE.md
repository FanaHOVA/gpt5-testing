# Task Manager Quick Reference

## Essential Commands

```bash
# Add tasks
tm add "Task title"                                    # Basic task
tm add "Task" -d "Description" -p high -a agent-1     # Detailed task
tm add "Subtask" --parent 1 --depends-on 2 3          # With dependencies

# View tasks  
tm list                      # All tasks
tm list -v                   # Detailed view
tm list -s pending          # Filter by status
tm list -a agent-1          # Filter by assignee

# Work on tasks
tm start 5                   # Mark as in_progress
tm complete 5                # Mark as completed
tm update 5 -s blocked      # Update status

# Check impacts
tm notifications             # Your notifications
tm show 5                    # Task details
```

## Status Values
- `pending` - Ready to work on
- `in_progress` - Currently being worked on  
- `completed` - Finished
- `blocked` - Waiting for dependencies
- `cancelled` - No longer needed

## Priority Levels
- `low` ○
- `medium` ◐ (default)
- `high` ●
- `critical` ⚠

## Tips
- Tasks are shared across all git worktrees
- Completing a task automatically unblocks dependents
- File references help track impact analysis
- Check notifications regularly for unblocked tasks