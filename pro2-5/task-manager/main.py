import typer
from typing import List, Optional
import json
from models import Task, TaskStatus
import os
from rich.console import Console
from rich.table import Table

app = typer.Typer()

TASKS_FILE = os.path.join(os.path.dirname(__file__), 'tasks.json')

def load_tasks() -> List[Task]:
    if not os.path.exists(TASKS_FILE):
        return []
    with open(TASKS_FILE, 'r') as f:
        tasks_data = json.load(f)
    return [Task(**task) for task in tasks_data]

def save_tasks(tasks: List[Task]):
    with open(TASKS_FILE, 'w') as f:
        json.dump([task.model_dump() for task in tasks], f, indent=4)

@app.command()
def create(
    title: str,
    description: Optional[str] = None,
    assignee: Optional[str] = None,
    dependencies: Optional[List[str]] = typer.Option(None, "--dependency", "-d"),
    file_path: Optional[str] = None,
):
    """
    Create a new task.
    """
    tasks = load_tasks()
    new_task = Task(
        title=title,
        description=description,
        assignee=assignee,
        dependencies=dependencies or [],
        file_path=file_path,
    )
    if new_task.dependencies:
        new_task.status = TaskStatus.BLOCKED
    tasks.append(new_task)
    save_tasks(tasks)
    print(f"Created task: {new_task.id} - {new_task.title}")

@app.command(name="list")
def list_tasks():
    """
    List all tasks in a table.
    """
    tasks = load_tasks()
    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=12)
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Assignee")
    table.add_column("Dependencies")
    table.add_column("File Path")

    status_colors = {
        TaskStatus.OPEN: "cyan",
        TaskStatus.IN_PROGRESS: "yellow",
        TaskStatus.BLOCKED: "red",
        TaskStatus.DONE: "green",
        TaskStatus.CANCELLED: "grey",
    }

    for task in tasks:
        status_color = status_colors.get(task.status, "white")
        dependencies = ", ".join([dep[:8] for dep in task.dependencies])
        table.add_row(
            task.id[:8],
            task.title,
            f"[{status_color}]{task.status.value}[/{status_color}]",
            task.assignee or "",
            dependencies,
            task.file_path or "",
        )

    console.print(table)

@app.command()
def update(
    task_id: str,
    title: Optional[str] = typer.Option(None, "--title", "-t"),
    description: Optional[str] = typer.Option(None, "--description", "-d"),
    status: Optional[TaskStatus] = typer.Option(None, "--status", "-s"),
    assignee: Optional[str] = typer.Option(None, "--assignee", "-a"),
    dependencies: Optional[List[str]] = typer.Option(None, "--dependency", "-dep"),
    file_path: Optional[str] = typer.Option(None, "--file-path", "-f"),
):
    """
    Update an existing task.
    """
    tasks = load_tasks()
    task_to_update = None
    for task in tasks:
        if task.id.startswith(task_id):
            task_to_update = task
            break

    if not task_to_update:
        print(f"Error: Task with ID starting with '{task_id}' not found.")
        raise typer.Exit(code=1)

    if title is not None:
        task_to_update.title = title
    if description is not None:
        task_to_update.description = description
    if status is not None:
        task_to_update.status = status
    if assignee is not None:
        task_to_update.assignee = assignee
    if dependencies is not None:
        task_to_update.dependencies = dependencies
    if file_path is not None:
        task_to_update.file_path = file_path

    save_tasks(tasks)
    print(f"Updated task: {task_to_update.id} - {task_to_update.title}")

@app.command()
def done(task_id: str):
    """
    Mark a task as done and unblock dependent tasks.
    """
    tasks = load_tasks()
    task_to_complete = None
    for task in tasks:
        if task.id.startswith(task_id):
            task_to_complete = task
            break

    if not task_to_complete:
        print(f"Error: Task with ID starting with '{task_id}' not found.")
        raise typer.Exit(code=1)

    task_to_complete.status = TaskStatus.DONE
    print(f"Completed task: {task_to_complete.id} - {task_to_complete.title}")

    # Unblock dependent tasks
    for task in tasks:
        if task_to_complete.id in task.dependencies:
            task.dependencies.remove(task_to_complete.id)
            if not task.dependencies:
                task.status = TaskStatus.OPEN
                print(f"Unblocked task: {task.id} - {task.title}")

    save_tasks(tasks)

if __name__ == "__main__":
    app()
