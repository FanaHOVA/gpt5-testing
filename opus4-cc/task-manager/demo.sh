#!/bin/bash
# Demo script for Task Manager

echo "=== Task Manager Demo ==="
echo "This demo shows how AI agents can collaborate using the task manager"
echo

# Clean up any existing data
rm -rf ~/.task-manager
mkdir -p ~/.task-manager

echo "1. Agent-1 creates a main feature task..."
./tm add "Implement REST API for user management" -p high -a agent-1
echo

echo "2. Agent-1 breaks it down into subtasks..."
./tm add "Design API endpoints and schemas" --parent 1 -a agent-1 -f docs/api-spec.yaml
./tm add "Implement database models" --parent 1 -a agent-2 -f src/models/user.py
./tm add "Create API handlers" --parent 1 --depends-on 2 3 -a agent-2 -f src/api/users.py
./tm add "Write unit tests" --parent 1 --depends-on 4 -a agent-3 -f tests/test_users.py
./tm add "Update API documentation" --parent 1 --depends-on 4 -a agent-1 -f docs/api.md
echo

echo "3. Current task list:"
./tm list -v
echo

echo "4. Agent-2 checks their assigned tasks..."
./tm list -a agent-2
echo

echo "5. Agent-1 completes the API design..."
./tm complete 2
echo

echo "6. Agent-2 starts working on database models..."
./tm start 3
./tm list -s in_progress
echo

echo "7. While working, agent-2 notices a potential improvement..."
./tm add "Optimize database indexes for user queries" \
  -d "Current schema missing indexes on frequently queried fields" \
  -f src/models/user.py -p medium -a agent-2
echo

echo "8. Agent-2 completes the database models..."
./tm complete 3
echo

echo "9. Agent-2 checks notifications (should see task 4 is now unblocked)..."
./tm notifications -a agent-2
echo

echo "10. Current status of all tasks:"
./tm list
echo

echo "11. Show details of the API handlers task:"
./tm show 4
echo

echo "=== Demo Complete ==="
echo "The task manager is now tracking your tasks in ~/.task-manager/"