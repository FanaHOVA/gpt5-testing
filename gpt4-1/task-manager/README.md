# GPT4-1 Task Manager

A minimal Python module for managing tasks with dependencies, notifications, and persistence to a JSON file. Includes a comprehensive test suite.

## Features

- **Task Model**: Each task has an ID, description, status, assignee, file/line reference, dependencies, dependents, notifications, and timestamps.
- **Persistence**: Tasks are saved to and loaded from a `tasks.json` file.
- **Dependency Tracking**: Tasks can depend on or be depended on by other tasks.
- **Notification Support**: Tasks can have a list of notification recipients.
- **Comprehensive Tests**: Includes tests for creation, serialization, dependencies, notifications, and persistence.

## File Structure

```
gpt4-1/
└── task-manager/
    ├── task.py         # Core Task class and persistence functions
    ├── test_task.py    # Pytest-based test suite
    └── tasks.json      # (Empty by default) JSON file for storing tasks
```

## Usage

### Task Model

```python
from task import Task

task = Task(
    id=1,
    description="Implement feature X",
    status="todo",
    assignee="alice",
    file="main.py",
    line=42,
    dependencies=[2, 3],
    dependents=[4],
    notifications=["bob@example.com"]
)
```

### Persistence

```python
from task import save_tasks, load_tasks

# Save a list of tasks
save_tasks([task])

# Load tasks from file
tasks = load_tasks()
```

## Running Tests

Tests are written using `pytest`. To run the test suite:

```bash
cd gpt4-1/task-manager
pytest test_task.py
```

## Notes

- The `tasks.json` file is empty by default and will be created/overwritten by `save_tasks`.
- The code is self-contained and does not require any external dependencies except `pytest` for testing.