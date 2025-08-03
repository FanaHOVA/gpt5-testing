#!/bin/bash
# Examples of task manager usage for AI agents

echo "Task Manager Examples"
echo "===================="
echo

# Set agent ID for this session
export TM_AGENT_ID="agent-main"

echo "1. Creating a main task with subtasks:"
echo "--------------------------------------"
./tm create "Implement REST API" --priority high
./tm create "Design API schema" --parent 1 --assignee agent-design
./tm create "Implement endpoints" --parent 1 --depends-on 2 --assignee agent-backend
./tm create "Write API tests" --parent 1 --depends-on 3 --assignee agent-test
./tm list --tree
echo

echo "2. Working with file references:"
echo "--------------------------------"
./tm create "Refactor database module" --files src/db.py src/models.py
./tm note "Consider using connection pooling" --file src/db.py:45 --task 5
./tm show 5
echo

echo "3. Managing dependencies:"
echo "------------------------"
./tm create "Update authentication" --priority high
./tm create "Add OAuth support" --depends-on 6
./tm create "Update user model" --depends-on 6
./tm blocked
echo

echo "4. Completing tasks and checking conflicts:"
echo "------------------------------------------"
# Complete the schema design task
./tm complete 2
# This should unblock the implementation task
./tm blocked
echo

echo "5. Different views and filters:"
echo "-------------------------------"
# Show my tasks
./tm list --assignee me
# Show high priority tasks
./tm list --status pending | grep -B2 -A2 "high"
# Show dependency graph
./tm deps 3
echo

echo "6. Export for reporting:"
echo "-----------------------"
./tm export tasks_backup.json
ls -la tasks_backup.json
echo

echo "7. Quick notes for improvements:"
echo "-------------------------------"
./tm note "TODO: Add rate limiting to all endpoints"
./tm note "FIXME: Memory leak in websocket handler" --file src/ws.py:120
./tm notes --limit 5