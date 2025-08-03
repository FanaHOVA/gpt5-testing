# Task Manager CLI

This is a command-line interface (CLI) tool for managing tasks. It is designed to be a simple and efficient way to keep track of your work, especially in a multi-agent environment.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Install the dependencies:**
    ```bash
    pip3 install -r task-manager/requirements.txt
    ```

## Usage

The Task Manager CLI provides the following commands:

### `create`

Create a new task.

```bash
python3 task-manager/main.py create <title> [OPTIONS]
```

**Options:**

*   `--description, -d TEXT`: The description of the task.
*   `--assignee, -a TEXT`: The person or agent assigned to the task.
*   `--dependency, -dep TEXT`: A task ID that this task depends on. Can be used multiple times.
*   `--file-path, -f TEXT`: The path to a file related to the task.

**Example:**

```bash
python3 task-manager/main.py create "Implement user authentication" --description "Add a login and registration system" --assignee "Agent 1"
```

### `list`

List all tasks in a table.

```bash
python3 task-manager/main.py list
```

**Example Output:**

```
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ ID           ┃ Title                               ┃ Status ┃ Assignee ┃ Dependencies ┃ File Path ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ e3aed6c4     │ Implement task creation and listing │ open   │          │              │           │
│ b2d9008b     │ Write documentation                 │ done   │          │              │           │
│ 345022f4     │ Release new version                 │ open   │          │              │           │
└──────────────┴─────────────────────────────────────┴────────┴──────────┴──────────────┴───────────┘
```

### `update`

Update an existing task.

```bash
python3 task-manager/main.py update <task-id> [OPTIONS]
```

**Options:**

*   `--title, -t TEXT`: The new title of the task.
*   `--description, -d TEXT`: The new description of the task.
*   `--status, -s [open|in_progress|blocked|done|cancelled]`: The new status of the task.
*   `--assignee, -a TEXT`: The new assignee of the task.
*   `--dependency, -dep TEXT`: A new task ID that this task depends on. Can be used multiple times.
*   `--file-path, -f TEXT`: The new file path for the task.

**Example:**

```bash
python3 task-manager/main.py update e3ae --status in_progress --assignee "Agent 2"
```

### `done`

Mark a task as done and unblock dependent tasks.

```bash
python3 task-manager/main.py done <task-id>
```

**Example:**

```bash
python3 task-manager/main.py done b2d9
```
