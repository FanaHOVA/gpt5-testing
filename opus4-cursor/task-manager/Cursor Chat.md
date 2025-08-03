# Designing a task manager for parallel agents
_Exported on [DATE REDACTED] at 11:58:16 PDT from Cursor (1.3.9)_

---

**User**


Task: Create a task manager to make yourself more effective at parallelism

Description:
You are an AI Engineer agent with the ability to spin up many instances of yourself in parallel. This allows you to tackle a lot of tasks at once, but also creates some delegation issues. All the different instances are usually in separate git worktrees and cannot see eachother's work.

To make yourself more productive, you should create a new local tool that allows you and your instances to be in sync. This tool will only be accessed by yourself through cli, so make sure it ergonomically fits that use case. It should feel like a unix utility.

Think through what interfaces it would need, possible failure modes, and the way your agents will interact with it. Some use cases to keep in mind:

You have a new task to work on, and want to create subtasks to hand off. Some of those subtasks might depend on eachother, and you want to make sure the agent who is blocked doesn't attempt to start until the other one is completed.

While doing a task, you notice there could be an improvement to be done in the codebase but it is out of scope for your current changes. You do want to make a note of it for the future though. It should be easy for you to add the task and reference what file it referred to. 

Whenever a task is done, the tracker should be updated. Also, all other outstanding tasks should be reviewed in case the new changes impact those in some way. For example one task might be looking to add a feature to an endpoint, but a task that just finished has now removed that endpoint. The agent working on that task should be notified in some way.

Also keep in mind the usual needs of tasks management like assignee, status, etc. 

Create a folder called `task-manager` in this folder and do all of your work inside of it.

---

**Cursor**

I'll help you create a task manager tool designed for AI agents working in parallel across different git worktrees. Let me start by exploring the current project structure and then design and implement this tool.

Now I'll design and implement a task manager tool tailored for AI agents working in parallel. Let me create the initial structure:

```markdown
# Task Manager for Parallel AI Agents

A Unix-style CLI tool for managing tasks across multiple AI agent instances working in different git worktrees.

## Features

- Create tasks and subtasks with dependencies
- Block tasks until dependencies are complete
- Add quick notes and improvements with file references
- Update task status and check for conflicts
- Designed for concurrent access across multiple worktrees

## Installation

```bash
cd task-manager
pip install -e .
```

## Usage

### Create a task
```bash
tm create "Implement user authentication" --priority high
tm create "Add login endpoint" --depends-on 1 --assignee agent-2
```

### List tasks
```bash
tm list                      # All tasks
tm list --status pending     # Filter by status
tm list --assignee me        # My tasks
```

### Update task status
```bash
tm update 1 --status in-progress
tm complete 1                # Mark as complete and check conflicts
```

### Add notes
```bash
tm note "Consider adding rate limiting" --file src/api.py:45 --task 1
```

### Check dependencies
```bash
tm deps 3                    # Show dependencies for task 3
tm blocked                   # Show all blocked tasks
```

### Resolve conflicts
```bash
tm check 1                   # Check if completed task 1 affects others
```

## Architecture

- Uses SQLite for centralized storage across worktrees
- File-based locking for concurrent access
- JSON export/import for task migration
- Git-aware file references
```

```python
from setuptools import setup, find_packages

setup(
    name="task-manager",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "rich>=10.0",
        "python-dateutil>=2.8",
    ],
    entry_points={
        "console_scripts": [
            "tm=task_manager.cli:cli",
        ],
    },
    python_requires=">=3.8",
)
```

```python
"""Task Manager for Parallel AI Agents"""

__version__ = "0.1.0"
```

```python
"""Database management for task storage."""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
import fcntl
import time
from typing import List, Dict, Optional, Any


class TaskDB:
    """SQLite-based task database with file locking for concurrent access."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection.
        
        Args:
            db_path: Path to database file. Defaults to ~/.task-manager/tasks.db
        """
        if db_path is None:
            db_dir = Path.home() / ".task-manager"
            db_dir.mkdir(exist_ok=True)
            db_path = db_dir / "tasks.db"
        
        self.db_path = db_path
        self.lock_path = db_path.with_suffix('.lock')
        self._init_db()
    
    @contextmanager
    def _lock(self):
        """Acquire exclusive lock for database operations."""
        lock_file = open(self.lock_path, 'w')
        max_retries = 10
        retry_delay = 0.1
        
        for i in range(max_retries):
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except IOError:
                if i == max_retries - 1:
                    raise RuntimeError("Could not acquire database lock")
                time.sleep(retry_delay)
        
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Tasks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority TEXT DEFAULT 'medium',
                    assignee TEXT,
                    worktree TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    parent_id INTEGER,
                    metadata TEXT,
                    FOREIGN KEY (parent_id) REFERENCES tasks(id)
                )
            """)
            
            # Dependencies table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dependencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    depends_on_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks(id),
                    FOREIGN KEY (depends_on_id) REFERENCES tasks(id),
                    UNIQUE(task_id, depends_on_id)
                )
            """)
            
            # Notes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    content TEXT NOT NULL,
                    file_ref TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            """)
            
            # Conflicts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    affected_task_id INTEGER NOT NULL,
                    description TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks(id),
                    FOREIGN KEY (affected_task_id) REFERENCES tasks(id)
                )
            """)
            
            conn.commit()
            conn.close()
    
    def create_task(self, title: str, description: str = None, 
                   priority: str = 'medium', assignee: str = None,
                   worktree: str = None, parent_id: int = None,
                   metadata: Dict[str, Any] = None) -> int:
        """Create a new task."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            metadata_json = json.dumps(metadata) if metadata else None
            
            cursor.execute("""
                INSERT INTO tasks (title, description, priority, assignee, 
                                 worktree, parent_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (title, description, priority, assignee, worktree, 
                  parent_id, metadata_json))
            
            task_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return task_id
    
    def add_dependency(self, task_id: int, depends_on_id: int):
        """Add a dependency between tasks."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO dependencies (task_id, depends_on_id)
                    VALUES (?, ?)
                """, (task_id, depends_on_id))
                conn.commit()
            except sqlite3.IntegrityError:
                # Dependency already exists
                pass
            finally:
                conn.close()
    
    def update_task(self, task_id: int, **kwargs):
        """Update task fields."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build update query
            fields = []
            values = []
            
            for field, value in kwargs.items():
                if field == 'metadata':
                    value = json.dumps(value) if value else None
                fields.append(f"{field} = ?")
                values.append(value)
            
            # Always update timestamp
            fields.append("updated_at = CURRENT_TIMESTAMP")
            
            # Add completed_at if status is changing to completed
            if kwargs.get('status') == 'completed':
                fields.append("completed_at = CURRENT_TIMESTAMP")
            
            values.append(task_id)
            
            query = f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?"
            cursor.execute(query, values)
            
            conn.commit()
            conn.close()
    
    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get a single task by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        
        if row:
            task = dict(row)
            if task['metadata']:
                task['metadata'] = json.loads(task['metadata'])
            
            # Get dependencies
            cursor.execute("""
                SELECT depends_on_id FROM dependencies 
                WHERE task_id = ?
            """, (task_id,))
            task['dependencies'] = [r[0] for r in cursor.fetchall()]
            
            # Get dependent tasks
            cursor.execute("""
                SELECT task_id FROM dependencies 
                WHERE depends_on_id = ?
            """, (task_id,))
            task['dependents'] = [r[0] for r in cursor.fetchall()]
            
            conn.close()
            return task
        
        conn.close()
        return None
    
    def list_tasks(self, status: str = None, assignee: str = None,
                   worktree: str = None, parent_id: int = None) -> List[Dict[str, Any]]:
        """List tasks with optional filters."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if assignee:
            query += " AND assignee = ?"
            params.append(assignee)
        if worktree:
            query += " AND worktree = ?"
            params.append(worktree)
        if parent_id is not None:
            query += " AND parent_id = ?"
            params.append(parent_id)
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        tasks = []
        
        for row in cursor.fetchall():
            task = dict(row)
            if task['metadata']:
                task['metadata'] = json.loads(task['metadata'])
            tasks.append(task)
        
        conn.close()
        return tasks
    
    def get_blocked_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks blocked by incomplete dependencies."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT t.*
            FROM tasks t
            JOIN dependencies d ON t.id = d.task_id
            JOIN tasks dep ON d.depends_on_id = dep.id
            WHERE t.status = 'pending' 
            AND dep.status != 'completed'
            ORDER BY t.created_at
        """)
        
        tasks = []
        for row in cursor.fetchall():
            task = dict(row)
            if task['metadata']:
                task['metadata'] = json.loads(task['metadata'])
            
            # Get blocking tasks
            cursor.execute("""
                SELECT dep.id, dep.title, dep.status
                FROM dependencies d
                JOIN tasks dep ON d.depends_on_id = dep.id
                WHERE d.task_id = ? AND dep.status != 'completed'
            """, (task['id'],))
            
            task['blocking_tasks'] = [dict(r) for r in cursor.fetchall()]
            tasks.append(task)
        
        conn.close()
        return tasks
    
    def add_note(self, content: str, task_id: int = None, 
                 file_ref: str = None, created_by: str = None):
        """Add a note, optionally attached to a task."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO notes (task_id, content, file_ref, created_by)
                VALUES (?, ?, ?, ?)
            """, (task_id, content, file_ref, created_by))
            
            note_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return note_id
    
    def get_notes(self, task_id: int = None) -> List[Dict[str, Any]]:
        """Get notes, optionally filtered by task."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if task_id:
            cursor.execute("""
                SELECT * FROM notes WHERE task_id = ? 
                ORDER BY created_at DESC
            """, (task_id,))
        else:
            cursor.execute("""
                SELECT * FROM notes ORDER BY created_at DESC
            """)
        
        notes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return notes
    
    def check_conflicts(self, completed_task_id: int) -> List[Dict[str, Any]]:
        """Check for potential conflicts with other tasks."""
        task = self.get_task(completed_task_id)
        if not task:
            return []
        
        conflicts = []
        
        # Get all pending/in-progress tasks
        active_tasks = self.list_tasks(status='pending') + \
                      self.list_tasks(status='in-progress')
        
        # Check for potential conflicts based on metadata
        task_metadata = task.get('metadata', {})
        affected_files = task_metadata.get('affected_files', [])
        
        for other_task in active_tasks:
            if other_task['id'] == completed_task_id:
                continue
            
            other_metadata = other_task.get('metadata', {})
            other_files = other_metadata.get('affected_files', [])
            
            # Check for file overlap
            if affected_files and other_files:
                overlap = set(affected_files) & set(other_files)
                if overlap:
                    conflicts.append({
                        'task_id': completed_task_id,
                        'affected_task_id': other_task['id'],
                        'affected_task_title': other_task['title'],
                        'type': 'file_overlap',
                        'details': list(overlap)
                    })
        
        # Record conflicts in database
        if conflicts:
            with self._lock():
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for conflict in conflicts:
                    cursor.execute("""
                        INSERT INTO conflicts (task_id, affected_task_id, description)
                        VALUES (?, ?, ?)
                    """, (conflict['task_id'], conflict['affected_task_id'],
                         json.dumps(conflict)))
                
                conn.commit()
                conn.close()
        
        return conflicts
    
    def export_tasks(self, output_file: Path):
        """Export all tasks to JSON."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        data = {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'tasks': [],
            'dependencies': [],
            'notes': []
        }
        
        # Export tasks
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks")
        for row in cursor.fetchall():
            task = dict(row)
            if task['metadata']:
                task['metadata'] = json.loads(task['metadata'])
            data['tasks'].append(task)
        
        # Export dependencies
        cursor.execute("SELECT * FROM dependencies")
        data['dependencies'] = [dict(row) for row in cursor.fetchall()]
        
        # Export notes
        cursor.execute("SELECT * FROM notes")
        data['notes'] = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
```

```python
"""Command-line interface for task manager."""

import click
import os
import json
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel
from rich.syntax import Syntax
from .database import TaskDB
from .utils import get_current_worktree, get_agent_id, format_file_ref


console = Console()
db = TaskDB()


@click.group()
@click.version_option()
def cli():
    """Task Manager for Parallel AI Agents.
    
    A Unix-style tool for managing tasks across multiple agent instances
    working in different git worktrees.
    """
    pass


@cli.command()
@click.argument('title')
@click.option('--description', '-d', help='Task description')
@click.option('--priority', '-p', type=click.Choice(['low', 'medium', 'high']), 
              default='medium', help='Task priority')
@click.option('--assignee', '-a', help='Assign to specific agent')
@click.option('--depends-on', '-D', multiple=True, type=int, 
              help='Task IDs this depends on')
@click.option('--parent', type=int, help='Parent task ID for subtasks')
@click.option('--files', '-f', multiple=True, help='Files this task affects')
def create(title, description, priority, assignee, depends_on, parent, files):
    """Create a new task."""
    worktree = get_current_worktree()
    
    # If no assignee specified, use current agent
    if not assignee:
        assignee = get_agent_id()
    
    metadata = {}
    if files:
        metadata['affected_files'] = list(files)
    
    # Create the task
    task_id = db.create_task(
        title=title,
        description=description,
        priority=priority,
        assignee=assignee,
        worktree=worktree,
        parent_id=parent,
        metadata=metadata if metadata else None
    )
    
    # Add dependencies
    for dep_id in depends_on:
        db.add_dependency(task_id, dep_id)
    
    console.print(f"[green]✓[/green] Created task #{task_id}: {title}")
    
    # Check if task is blocked
    if depends_on:
        blocked_by = []
        for dep_id in depends_on:
            dep_task = db.get_task(dep_id)
            if dep_task and dep_task['status'] != 'completed':
                blocked_by.append(f"#{dep_id} ({dep_task['title']})")
        
        if blocked_by:
            console.print(f"[yellow]⚠[/yellow] Task is blocked by: {', '.join(blocked_by)}")


@cli.command()
@click.option('--status', '-s', type=click.Choice(['pending', 'in-progress', 'completed', 'cancelled']),
              help='Filter by status')
@click.option('--assignee', '-a', help='Filter by assignee')
@click.option('--worktree', '-w', help='Filter by worktree')
@click.option('--parent', type=int, help='Show subtasks of parent')
@click.option('--tree', '-t', is_flag=True, help='Show as tree view')
def list(status, assignee, worktree, parent, tree):
    """List tasks with optional filters."""
    # Handle special assignee values
    if assignee == 'me':
        assignee = get_agent_id()
    
    tasks = db.list_tasks(
        status=status,
        assignee=assignee,
        worktree=worktree,
        parent_id=parent
    )
    
    if not tasks:
        console.print("[dim]No tasks found[/dim]")
        return
    
    if tree:
        _show_task_tree(tasks)
    else:
        _show_task_table(tasks)


def _show_task_table(tasks):
    """Display tasks in a table format."""
    table = Table(title="Tasks")
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Title", style="white")
    table.add_column("Status", width=12)
    table.add_column("Priority", width=8)
    table.add_column("Assignee", width=12)
    table.add_column("Created", width=10)
    
    status_colors = {
        'pending': 'yellow',
        'in-progress': 'blue',
        'completed': 'green',
        'cancelled': 'red'
    }
    
    priority_colors = {
        'low': 'dim',
        'medium': 'white',
        'high': 'red'
    }
    
    for task in tasks:
        status_color = status_colors.get(task['status'], 'white')
        priority_color = priority_colors.get(task['priority'], 'white')
        
        created = datetime.fromisoformat(task['created_at']).strftime('%Y-%m-%d')
        
        table.add_row(
            str(task['id']),
            task['title'][:50] + '...' if len(task['title']) > 50 else task['title'],
            f"[{status_color}]{task['status']}[/{status_color}]",
            f"[{priority_color}]{task['priority']}[/{priority_color}]",
            task['assignee'] or '-',
            created
        )
    
    console.print(table)


def _show_task_tree(tasks):
    """Display tasks in a tree format."""
    # Build parent-child relationships
    root_tasks = [t for t in tasks if t['parent_id'] is None]
    child_map = {}
    for task in tasks:
        if task['parent_id']:
            if task['parent_id'] not in child_map:
                child_map[task['parent_id']] = []
            child_map[task['parent_id']].append(task)
    
    tree = Tree("Tasks")
    
    def add_task_to_tree(parent_node, task):
        status_icon = {
            'pending': '○',
            'in-progress': '◐',
            'completed': '●',
            'cancelled': '✗'
        }
        icon = status_icon.get(task['status'], '?')
        
        node_text = f"{icon} #{task['id']} {task['title']}"
        if task['assignee']:
            node_text += f" [{task['assignee']}]"
        
        node = parent_node.add(node_text)
        
        # Add children
        for child in child_map.get(task['id'], []):
            add_task_to_tree(node, child)
    
    for task in root_tasks:
        add_task_to_tree(tree, task)
    
    console.print(tree)


@cli.command()
@click.argument('task_id', type=int)
@click.option('--status', '-s', type=click.Choice(['pending', 'in-progress', 'completed', 'cancelled']))
@click.option('--assignee', '-a', help='Reassign to different agent')
@click.option('--priority', '-p', type=click.Choice(['low', 'medium', 'high']))
@click.option('--add-files', '-f', multiple=True, help='Add affected files')
def update(task_id, status, assignee, priority, add_files):
    """Update task properties."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]✗[/red] Task #{task_id} not found")
        return
    
    updates = {}
    if status:
        updates['status'] = status
    if assignee:
        if assignee == 'me':
            assignee = get_agent_id()
        updates['assignee'] = assignee
    if priority:
        updates['priority'] = priority
    
    # Handle file additions
    if add_files:
        metadata = task.get('metadata', {})
        affected_files = set(metadata.get('affected_files', []))
        affected_files.update(add_files)
        metadata['affected_files'] = list(affected_files)
        updates['metadata'] = metadata
    
    if updates:
        db.update_task(task_id, **updates)
        console.print(f"[green]✓[/green] Updated task #{task_id}")
        
        # If marking as complete, check for conflicts
        if status == 'completed':
            _check_and_show_conflicts(task_id)
    else:
        console.print("[yellow]No updates specified[/yellow]")


@cli.command()
@click.argument('task_id', type=int)
def complete(task_id):
    """Mark a task as completed and check for conflicts."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]✗[/red] Task #{task_id} not found")
        return
    
    if task['status'] == 'completed':
        console.print(f"[yellow]Task #{task_id} is already completed[/yellow]")
        return
    
    # Update status
    db.update_task(task_id, status='completed')
    console.print(f"[green]✓[/green] Completed task #{task_id}: {task['title']}")
    
    # Check for unblocked tasks
    unblocked = []
    for dependent_id in task.get('dependents', []):
        dependent = db.get_task(dependent_id)
        if dependent and dependent['status'] == 'pending':
            # Check if all dependencies are now complete
            all_complete = True
            for dep_id in dependent.get('dependencies', []):
                dep = db.get_task(dep_id)
                if dep and dep['status'] != 'completed':
                    all_complete = False
                    break
            
            if all_complete:
                unblocked.append(f"#{dependent_id} ({dependent['title']})")
    
    if unblocked:
        console.print(f"[cyan]→[/cyan] Unblocked tasks: {', '.join(unblocked)}")
    
    # Check for conflicts
    _check_and_show_conflicts(task_id)


def _check_and_show_conflicts(task_id):
    """Check and display any conflicts caused by task completion."""
    conflicts = db.check_conflicts(task_id)
    
    if conflicts:
        console.print("\n[yellow]⚠ Potential conflicts detected:[/yellow]")
        for conflict in conflicts:
            console.print(f"  • Task #{conflict['affected_task_id']} ({conflict['affected_task_title']})")
            if conflict['type'] == 'file_overlap':
                console.print(f"    Shared files: {', '.join(conflict['details'])}")


@cli.command()
@click.argument('content')
@click.option('--task', '-t', type=int, help='Attach to specific task')
@click.option('--file', '-f', help='File reference (e.g., src/api.py:45)')
def note(content, task, file):
    """Add a quick note or improvement idea."""
    agent_id = get_agent_id()
    
    # Parse and validate file reference if provided
    file_ref = None
    if file:
        file_ref = format_file_ref(file)
    
    note_id = db.add_note(
        content=content,
        task_id=task,
        file_ref=file_ref,
        created_by=agent_id
    )
    
    console.print(f"[green]✓[/green] Added note #{note_id}")
    
    if task:
        console.print(f"  → Attached to task #{task}")
    if file_ref:
        console.print(f"  → References: {file_ref}")


@cli.command()
@click.argument('task_id', type=int)
def show(task_id):
    """Show detailed information about a task."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]✗[/red] Task #{task_id} not found")
        return
    
    # Build task details panel
    details = []
    details.append(f"[bold]Title:[/bold] {task['title']}")
    if task['description']:
        details.append(f"[bold]Description:[/bold] {task['description']}")
    details.append(f"[bold]Status:[/bold] {task['status']}")
    details.append(f"[bold]Priority:[/bold] {task['priority']}")
    details.append(f"[bold]Assignee:[/bold] {task['assignee'] or 'Unassigned'}")
    details.append(f"[bold]Worktree:[/bold] {task['worktree'] or 'Unknown'}")
    details.append(f"[bold]Created:[/bold] {task['created_at']}")
    
    if task['updated_at'] != task['created_at']:
        details.append(f"[bold]Updated:[/bold] {task['updated_at']}")
    
    if task['completed_at']:
        details.append(f"[bold]Completed:[/bold] {task['completed_at']}")
    
    panel = Panel('\n'.join(details), title=f"Task #{task_id}", border_style="blue")
    console.print(panel)
    
    # Show dependencies
    if task['dependencies']:
        console.print("\n[bold]Dependencies:[/bold]")
        for dep_id in task['dependencies']:
            dep = db.get_task(dep_id)
            if dep:
                status_icon = '✓' if dep['status'] == 'completed' else '○'
                console.print(f"  {status_icon} #{dep_id}: {dep['title']} [{dep['status']}]")
    
    # Show dependents
    if task['dependents']:
        console.print("\n[bold]Dependent tasks:[/bold]")
        for dep_id in task['dependents']:
            dep = db.get_task(dep_id)
            if dep:
                console.print(f"  • #{dep_id}: {dep['title']} [{dep['status']}]")
    
    # Show affected files
    metadata = task.get('metadata', {})
    affected_files = metadata.get('affected_files', [])
    if affected_files:
        console.print("\n[bold]Affected files:[/bold]")
        for file in affected_files:
            console.print(f"  • {file}")
    
    # Show notes
    notes = db.get_notes(task_id)
    if notes:
        console.print("\n[bold]Notes:[/bold]")
        for note in notes:
            console.print(f"  • {note['content']}")
            if note['file_ref']:
                console.print(f"    → {note['file_ref']}")
            console.print(f"    [dim]{note['created_at']} by {note['created_by'] or 'Unknown'}[/dim]")


@cli.command()
def blocked():
    """Show all tasks blocked by dependencies."""
    blocked_tasks = db.get_blocked_tasks()
    
    if not blocked_tasks:
        console.print("[green]No blocked tasks![/green]")
        return
    
    console.print("[yellow]Blocked tasks:[/yellow]\n")
    
    for task in blocked_tasks:
        console.print(f"[bold]#{task['id']}:[/bold] {task['title']}")
        console.print(f"  Assignee: {task['assignee'] or 'Unassigned'}")
        console.print("  Blocked by:")
        
        for blocker in task['blocking_tasks']:
            console.print(f"    • #{blocker['id']}: {blocker['title']} [{blocker['status']}]")
        
        console.print()


@cli.command()
@click.argument('task_id', type=int)
@click.argument('depends_on_ids', type=int, nargs=-1, required=True)
def depend(task_id, depends_on_ids):
    """Add dependencies to a task."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]✗[/red] Task #{task_id} not found")
        return
    
    added = []
    for dep_id in depends_on_ids:
        dep = db.get_task(dep_id)
        if not dep:
            console.print(f"[yellow]⚠[/yellow] Task #{dep_id} not found, skipping")
            continue
        
        db.add_dependency(task_id, dep_id)
        added.append(f"#{dep_id}")
    
    if added:
        console.print(f"[green]✓[/green] Added dependencies: {', '.join(added)}")


@cli.command()
@click.argument('task_id', type=int)
def deps(task_id):
    """Show dependency graph for a task."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]✗[/red] Task #{task_id} not found")
        return
    
    # Build dependency tree
    tree = Tree(f"#{task_id}: {task['title']}")
    
    # Add upstream dependencies
    if task['dependencies']:
        deps_node = tree.add("[bold]Depends on:[/bold]")
        for dep_id in task['dependencies']:
            dep = db.get_task(dep_id)
            if dep:
                status_icon = '✓' if dep['status'] == 'completed' else '○'
                deps_node.add(f"{status_icon} #{dep_id}: {dep['title']}")
    
    # Add downstream dependents
    if task['dependents']:
        deps_node = tree.add("[bold]Required by:[/bold]")
        for dep_id in task['dependents']:
            dep = db.get_task(dep_id)
            if dep:
                status_icon = '✓' if dep['status'] == 'completed' else '○'
                deps_node.add(f"{status_icon} #{dep_id}: {dep['title']}")
    
    console.print(tree)


@cli.command()
@click.argument('task_id', type=int)
def check(task_id):
    """Check for conflicts with a specific task."""
    conflicts = db.check_conflicts(task_id)
    
    if not conflicts:
        console.print(f"[green]✓[/green] No conflicts found for task #{task_id}")
        return
    
    console.print(f"[yellow]Conflicts for task #{task_id}:[/yellow]\n")
    
    for conflict in conflicts:
        console.print(f"• Affects task #{conflict['affected_task_id']} ({conflict['affected_task_title']})")
        if conflict['type'] == 'file_overlap':
            console.print(f"  Shared files: {', '.join(conflict['details'])}")


@cli.command()
@click.argument('output_file', type=click.Path())
def export(output_file):
    """Export all tasks to JSON file."""
    output_path = Path(output_file)
    db.export_tasks(output_path)
    console.print(f"[green]✓[/green] Exported tasks to {output_file}")


@cli.command()
@click.option('--limit', '-n', type=int, default=10, help='Number of notes to show')
@click.option('--task', '-t', type=int, help='Filter by task ID')
def notes(limit, task):
    """List recent notes."""
    all_notes = db.get_notes(task)
    
    if not all_notes:
        console.print("[dim]No notes found[/dim]")
        return
    
    # Apply limit
    notes_to_show = all_notes[:limit]
    
    console.print(f"[bold]Recent Notes[/bold] (showing {len(notes_to_show)} of {len(all_notes)})\n")
    
    for note in notes_to_show:
        console.print(f"[cyan]#{note['id']}[/cyan] {note['content']}")
        
        details = []
        if note['task_id']:
            task = db.get_task(note['task_id'])
            if task:
                details.append(f"Task #{note['task_id']}: {task['title']}")
        
        if note['file_ref']:
            details.append(f"File: {note['file_ref']}")
        
        if details:
            console.print(f"  → {' | '.join(details)}")
        
        console.print(f"  [dim]{note['created_at']} by {note['created_by'] or 'Unknown'}[/dim]\n")


if __name__ == '__main__':
    cli()
```

```python
"""Utility functions for task manager."""

import os
import subprocess
import re
from pathlib import Path
from typing import Optional


def get_current_worktree() -> Optional[str]:
    """Get the current git worktree path."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        # Not in a git repository
        return None


def get_agent_id() -> str:
    """Get the current agent identifier.
    
    Uses environment variable TM_AGENT_ID if set, otherwise uses the 
    current user and hostname.
    """
    agent_id = os.environ.get('TM_AGENT_ID')
    if agent_id:
        return agent_id
    
    # Fallback to user@hostname
    import socket
    user = os.environ.get('USER', 'unknown')
    hostname = socket.gethostname().split('.')[0]  # Just the short hostname
    return f"{user}@{hostname}"


def format_file_ref(file_ref: str) -> str:
    """Format a file reference to a standard format.
    
    Accepts formats like:
    - path/to/file.py
    - path/to/file.py:42
    - path/to/file.py:42-50
    - path/to/file.py#L42
    
    Returns: Normalized format path/to/file.py:42 or path/to/file.py:42-50
    """
    # Remove any leading/trailing whitespace
    file_ref = file_ref.strip()
    
    # Handle GitHub-style line references (#L42)
    file_ref = re.sub(r'#L(\d+)', r':\1', file_ref)
    
    # Validate the format
    if not re.match(r'^[^:]+(?::\d+(?:-\d+)?)?$', file_ref):
        return file_ref  # Return as-is if it doesn't match expected format
    
    # Make path relative if it's absolute and within current worktree
    parts = file_ref.split(':', 1)
    path = Path(parts[0])
    
    if path.is_absolute():
        worktree = get_current_worktree()
        if worktree:
            try:
                path = path.relative_to(worktree)
                parts[0] = str(path)
                file_ref = ':'.join(parts)
            except ValueError:
                # Path is not within worktree
                pass
    
    return file_ref


def parse_file_ref(file_ref: str) -> dict:
    """Parse a file reference into components.
    
    Returns dict with keys:
    - path: The file path
    - line_start: Starting line number (if specified)
    - line_end: Ending line number (if range specified)
    """
    match = re.match(r'^([^:]+)(?::(\d+)(?:-(\d+))?)?$', file_ref)
    if not match:
        return {'path': file_ref, 'line_start': None, 'line_end': None}
    
    path, line_start, line_end = match.groups()
    
    result = {'path': path}
    if line_start:
        result['line_start'] = int(line_start)
        result['line_end'] = int(line_end) if line_end else int(line_start)
    else:
        result['line_start'] = None
        result['line_end'] = None
    
    return result


def get_git_branch() -> Optional[str]:
    """Get the current git branch name."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_modified_files() -> list:
    """Get list of files modified in the current worktree."""
    try:
        # Get staged files
        staged = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Get unstaged files
        unstaged = subprocess.run(
            ['git', 'diff', '--name-only'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Get untracked files
        untracked = subprocess.run(
            ['git', 'ls-files', '--others', '--exclude-standard'],
            capture_output=True,
            text=True,
            check=True
        )
        
        files = set()
        files.update(staged.stdout.strip().split('\n'))
        files.update(unstaged.stdout.strip().split('\n'))
        files.update(untracked.stdout.strip().split('\n'))
        
        # Remove empty strings
        files.discard('')
        
        return sorted(list(files))
    except subprocess.CalledProcessError:
        return []
```

Now let me create a test script to verify the functionality:

```python
#!/usr/bin/env python3
"""Test script for task manager functionality."""

import subprocess
import sys
import time
from pathlib import Path


def run_tm(args):
    """Run tm command and return output."""
    cmd = ['python', '-m', 'task_manager.cli'] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def test_basic_operations():
    """Test basic task manager operations."""
    print("Testing Task Manager...")
    print("-" * 50)
    
    # Test 1: Create a simple task
    print("\n1. Creating a simple task...")
    code, out, err = run_tm(['create', 'Implement user authentication', '-p', 'high'])
    if code == 0:
        print("✓ Task created successfully")
        print(out)
    else:
        print("✗ Failed to create task")
        print(err)
        return False
    
    # Test 2: Create a task with dependencies
    print("\n2. Creating a task with dependencies...")
    code, out, err = run_tm(['create', 'Add login endpoint', '-D', '1', '-a', 'agent-2'])
    if code == 0:
        print("✓ Dependent task created")
        print(out)
    else:
        print("✗ Failed to create dependent task")
        print(err)
    
    # Test 3: List tasks
    print("\n3. Listing all tasks...")
    code, out, err = run_tm(['list'])
    if code == 0:
        print("✓ Tasks listed")
        print(out)
    else:
        print("✗ Failed to list tasks")
        print(err)
    
    # Test 4: Show blocked tasks
    print("\n4. Showing blocked tasks...")
    code, out, err = run_tm(['blocked'])
    if code == 0:
        print("✓ Blocked tasks shown")
        print(out)
    else:
        print("✗ Failed to show blocked tasks")
        print(err)
    
    # Test 5: Add a note
    print("\n5. Adding a note...")
    code, out, err = run_tm(['note', 'Consider adding rate limiting', '-f', 'src/api.py:45', '-t', '1'])
    if code == 0:
        print("✓ Note added")
        print(out)
    else:
        print("✗ Failed to add note")
        print(err)
    
    # Test 6: Update task status
    print("\n6. Updating task status...")
    code, out, err = run_tm(['update', '1', '-s', 'in-progress'])
    if code == 0:
        print("✓ Task updated")
        print(out)
    else:
        print("✗ Failed to update task")
        print(err)
    
    # Test 7: Show task details
    print("\n7. Showing task details...")
    code, out, err = run_tm(['show', '1'])
    if code == 0:
        print("✓ Task details shown")
        print(out)
    else:
        print("✗ Failed to show task details")
        print(err)
    
    # Test 8: Complete a task
    print("\n8. Completing task...")
    code, out, err = run_tm(['complete', '1'])
    if code == 0:
        print("✓ Task completed")
        print(out)
    else:
        print("✗ Failed to complete task")
        print(err)
    
    # Test 9: Show dependency tree
    print("\n9. Showing dependency tree...")
    code, out, err = run_tm(['deps', '2'])
    if code == 0:
        print("✓ Dependencies shown")
        print(out)
    else:
        print("✗ Failed to show dependencies")
        print(err)
    
    # Test 10: List with tree view
    print("\n10. Listing tasks in tree view...")
    code, out, err = run_tm(['list', '--tree'])
    if code == 0:
        print("✓ Tree view shown")
        print(out)
    else:
        print("✗ Failed to show tree view")
        print(err)
    
    print("\n" + "-" * 50)
    print("All tests completed!")
    return True


if __name__ == '__main__':
    test_basic_operations()
```

Let me install the package and run some tests:

Now let me test the `tm` command:

Let me check where the script was installed:

Let me run the test script to verify all functionality:

```python
#!/usr/bin/env python3
"""Test script for task manager functionality."""

import subprocess
import sys
import time
from pathlib import Path


def run_tm(args):
    """Run tm command and return output."""
    cmd = ['python3', '-m', 'task_manager.cli'] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def test_basic_operations():
    """Test basic task manager operations."""
    print("Testing Task Manager...")
    print("-" * 50)
    
    # Test 1: Create a simple task
    print("\n1. Creating a simple task...")
    code, out, err = run_tm(['create', 'Implement user authentication', '-p', 'high'])
    if code == 0:
        print("✓ Task created successfully")
        print(out)
    else:
        print("✗ Failed to create task")
        print(err)
        return False
    
    # Test 2: Create a task with dependencies
    print("\n2. Creating a task with dependencies...")
    code, out, err = run_tm(['create', 'Add login endpoint', '-D', '1', '-a', 'agent-2'])
    if code == 0:
        print("✓ Dependent task created")
        print(out)
    else:
        print("✗ Failed to create dependent task")
        print(err)
    
    # Test 3: List tasks
    print("\n3. Listing all tasks...")
    code, out, err = run_tm(['list'])
    if code == 0:
        print("✓ Tasks listed")
        print(out)
    else:
        print("✗ Failed to list tasks")
        print(err)
    
    # Test 4: Show blocked tasks
    print("\n4. Showing blocked tasks...")
    code, out, err = run_tm(['blocked'])
    if code == 0:
        print("✓ Blocked tasks shown")
        print(out)
    else:
        print("✗ Failed to show blocked tasks")
        print(err)
    
    # Test 5: Add a note
    print("\n5. Adding a note...")
    code, out, err = run_tm(['note', 'Consider adding rate limiting', '-f', 'src/api.py:45', '-t', '1'])
    if code == 0:
        print("✓ Note added")
        print(out)
    else:
        print("✗ Failed to add note")
        print(err)
    
    # Test 6: Update task status
    print("\n6. Updating task status...")
    code, out, err = run_tm(['update', '1', '-s', 'in-progress'])
    if code == 0:
        print("✓ Task updated")
        print(out)
    else:
        print("✗ Failed to update task")
        print(err)
    
    # Test 7: Show task details
    print("\n7. Showing task details...")
    code, out, err = run_tm(['show', '1'])
    if code == 0:
        print("✓ Task details shown")
        print(out)
    else:
        print("✗ Failed to show task details")
        print(err)
    
    # Test 8: Complete a task
    print("\n8. Completing task...")
    code, out, err = run_tm(['complete', '1'])
    if code == 0:
        print("✓ Task completed")
        print(out)
    else:
        print("✗ Failed to complete task")
        print(err)
    
    # Test 9: Show dependency tree
    print("\n9. Showing dependency tree...")
    code, out, err = run_tm(['deps', '2'])
    if code == 0:
        print("✓ Dependencies shown")
        print(out)
    else:
        print("✗ Failed to show dependencies")
        print(err)
    
    # Test 10: List with tree view
    print("\n10. Listing tasks in tree view...")
    code, out, err = run_tm(['list', '--tree'])
    if code == 0:
        print("✓ Tree view shown")
        print(out)
    else:
        print("✗ Failed to show tree view")
        print(err)
    
    print("\n" + "-" * 50)
    print("All tests completed!")
    return True


if __name__ == '__main__':
    test_basic_operations()
```

I see there are some bugs with None metadata handling. Let me fix these issues:

```python
"""Command-line interface for task manager."""

import click
import os
import json
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel
from rich.syntax import Syntax
from .database import TaskDB
from .utils import get_current_worktree, get_agent_id, format_file_ref


console = Console()
db = TaskDB()


@click.group()
@click.version_option()
def cli():
    """Task Manager for Parallel AI Agents.
    
    A Unix-style tool for managing tasks across multiple agent instances
    working in different git worktrees.
    """
    pass


@cli.command()
@click.argument('title')
@click.option('--description', '-d', help='Task description')
@click.option('--priority', '-p', type=click.Choice(['low', 'medium', 'high']), 
              default='medium', help='Task priority')
@click.option('--assignee', '-a', help='Assign to specific agent')
@click.option('--depends-on', '-D', multiple=True, type=int, 
              help='Task IDs this depends on')
@click.option('--parent', type=int, help='Parent task ID for subtasks')
@click.option('--files', '-f', multiple=True, help='Files this task affects')
def create(title, description, priority, assignee, depends_on, parent, files):
    """Create a new task."""
    worktree = get_current_worktree()
    
    # If no assignee specified, use current agent
    if not assignee:
        assignee = get_agent_id()
    
    metadata = {}
    if files:
        metadata['affected_files'] = list(files)
    
    # Create the task
    task_id = db.create_task(
        title=title,
        description=description,
        priority=priority,
        assignee=assignee,
        worktree=worktree,
        parent_id=parent,
        metadata=metadata if metadata else None
    )
    
    # Add dependencies
    for dep_id in depends_on:
        db.add_dependency(task_id, dep_id)
    
    console.print(f"[green]✓[/green] Created task #{task_id}: {title}")
    
    # Check if task is blocked
    if depends_on:
        blocked_by = []
        for dep_id in depends_on:
            dep_task = db.get_task(dep_id)
            if dep_task and dep_task['status'] != 'completed':
                blocked_by.append(f"#{dep_id} ({dep_task['title']})")
        
        if blocked_by:
            console.print(f"[yellow]⚠[/yellow] Task is blocked by: {', '.join(blocked_by)}")


@cli.command()
@click.option('--status', '-s', type=click.Choice(['pending', 'in-progress', 'completed', 'cancelled']),
              help='Filter by status')
@click.option('--assignee', '-a', help='Filter by assignee')
@click.option('--worktree', '-w', help='Filter by worktree')
@click.option('--parent', type=int, help='Show subtasks of parent')
@click.option('--tree', '-t', is_flag=True, help='Show as tree view')
def list(status, assignee, worktree, parent, tree):
    """List tasks with optional filters."""
    # Handle special assignee values
    if assignee == 'me':
        assignee = get_agent_id()
    
    tasks = db.list_tasks(
        status=status,
        assignee=assignee,
        worktree=worktree,
        parent_id=parent
    )
    
    if not tasks:
        console.print("[dim]No tasks found[/dim]")
        return
    
    if tree:
        _show_task_tree(tasks)
    else:
        _show_task_table(tasks)


def _show_task_table(tasks):
    """Display tasks in a table format."""
    table = Table(title="Tasks")
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Title", style="white")
    table.add_column("Status", width=12)
    table.add_column("Priority", width=8)
    table.add_column("Assignee", width=12)
    table.add_column("Created", width=10)
    
    status_colors = {
        'pending': 'yellow',
        'in-progress': 'blue',
        'completed': 'green',
        'cancelled': 'red'
    }
    
    priority_colors = {
        'low': 'dim',
        'medium': 'white',
        'high': 'red'
    }
    
    for task in tasks:
        status_color = status_colors.get(task['status'], 'white')
        priority_color = priority_colors.get(task['priority'], 'white')
        
        created = datetime.fromisoformat(task['created_at']).strftime('%Y-%m-%d')
        
        table.add_row(
            str(task['id']),
            task['title'][:50] + '...' if len(task['title']) > 50 else task['title'],
            f"[{status_color}]{task['status']}[/{status_color}]",
            f"[{priority_color}]{task['priority']}[/{priority_color}]",
            task['assignee'] or '-',
            created
        )
    
    console.print(table)


def _show_task_tree(tasks):
    """Display tasks in a tree format."""
    # Build parent-child relationships
    root_tasks = [t for t in tasks if t['parent_id'] is None]
    child_map = {}
    for task in tasks:
        if task['parent_id']:
            if task['parent_id'] not in child_map:
                child_map[task['parent_id']] = []
            child_map[task['parent_id']].append(task)
    
    tree = Tree("Tasks")
    
    def add_task_to_tree(parent_node, task):
        status_icon = {
            'pending': '○',
            'in-progress': '◐',
            'completed': '●',
            'cancelled': '✗'
        }
        icon = status_icon.get(task['status'], '?')
        
        node_text = f"{icon} #{task['id']} {task['title']}"
        if task['assignee']:
            node_text += f" [{task['assignee']}]"
        
        node = parent_node.add(node_text)
        
        # Add children
        for child in child_map.get(task['id'], []):
            add_task_to_tree(node, child)
    
    for task in root_tasks:
        add_task_to_tree(tree, task)
    
    console.print(tree)


@cli.command()
@click.argument('task_id', type=int)
@click.option('--status', '-s', type=click.Choice(['pending', 'in-progress', 'completed', 'cancelled']))
@click.option('--assignee', '-a', help='Reassign to different agent')
@click.option('--priority', '-p', type=click.Choice(['low', 'medium', 'high']))
@click.option('--add-files', '-f', multiple=True, help='Add affected files')
def update(task_id, status, assignee, priority, add_files):
    """Update task properties."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]✗[/red] Task #{task_id} not found")
        return
    
    updates = {}
    if status:
        updates['status'] = status
    if assignee:
        if assignee == 'me':
            assignee = get_agent_id()
        updates['assignee'] = assignee
    if priority:
        updates['priority'] = priority
    
    # Handle file additions
    if add_files:
        metadata = task.get('metadata', {})
        affected_files = set(metadata.get('affected_files', []))
        affected_files.update(add_files)
        metadata['affected_files'] = list(affected_files)
        updates['metadata'] = metadata
    
    if updates:
        db.update_task(task_id, **updates)
        console.print(f"[green]✓[/green] Updated task #{task_id}")
        
        # If marking as complete, check for conflicts
        if status == 'completed':
            _check_and_show_conflicts(task_id)
    else:
        console.print("[yellow]No updates specified[/yellow]")


@cli.command()
@click.argument('task_id', type=int)
def complete(task_id):
    """Mark a task as completed and check for conflicts."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]✗[/red] Task #{task_id} not found")
        return
    
    if task['status'] == 'completed':
        console.print(f"[yellow]Task #{task_id} is already completed[/yellow]")
        return
    
    # Update status
    db.update_task(task_id, status='completed')
    console.print(f"[green]✓[/green] Completed task #{task_id}: {task['title']}")
    
    # Check for unblocked tasks
    unblocked = []
    for dependent_id in task.get('dependents', []):
        dependent = db.get_task(dependent_id)
        if dependent and dependent['status'] == 'pending':
            # Check if all dependencies are now complete
            all_complete = True
            for dep_id in dependent.get('dependencies', []):
                dep = db.get_task(dep_id)
                if dep and dep['status'] != 'completed':
                    all_complete = False
                    break
            
            if all_complete:
                unblocked.append(f"#{dependent_id} ({dependent['title']})")
    
    if unblocked:
        console.print(f"[cyan]→[/cyan] Unblocked tasks: {', '.join(unblocked)}")
    
    # Check for conflicts
    _check_and_show_conflicts(task_id)


def _check_and_show_conflicts(task_id):
    """Check and display any conflicts caused by task completion."""
    conflicts = db.check_conflicts(task_id)
    
    if conflicts:
        console.print("\n[yellow]⚠ Potential conflicts detected:[/yellow]")
        for conflict in conflicts:
            console.print(f"  • Task #{conflict['affected_task_id']} ({conflict['affected_task_title']})")
            if conflict['type'] == 'file_overlap':
                console.print(f"    Shared files: {', '.join(conflict['details'])}")


@cli.command()
@click.argument('content')
@click.option('--task', '-t', type=int, help='Attach to specific task')
@click.option('--file', '-f', help='File reference (e.g., src/api.py:45)')
def note(content, task, file):
    """Add a quick note or improvement idea."""
    agent_id = get_agent_id()
    
    # Parse and validate file reference if provided
    file_ref = None
    if file:
        file_ref = format_file_ref(file)
    
    note_id = db.add_note(
        content=content,
        task_id=task,
        file_ref=file_ref,
        created_by=agent_id
    )
    
    console.print(f"[green]✓[/green] Added note #{note_id}")
    
    if task:
        console.print(f"  → Attached to task #{task}")
    if file_ref:
        console.print(f"  → References: {file_ref}")


@cli.command()
@click.argument('task_id', type=int)
def show(task_id):
    """Show detailed information about a task."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]✗[/red] Task #{task_id} not found")
        return
    
    # Build task details panel
    details = []
    details.append(f"[bold]Title:[/bold] {task['title']}")
    if task['description']:
        details.append(f"[bold]Description:[/bold] {task['description']}")
    details.append(f"[bold]Status:[/bold] {task['status']}")
    details.append(f"[bold]Priority:[/bold] {task['priority']}")
    details.append(f"[bold]Assignee:[/bold] {task['assignee'] or 'Unassigned'}")
    details.append(f"[bold]Worktree:[/bold] {task['worktree'] or 'Unknown'}")
    details.append(f"[bold]Created:[/bold] {task['created_at']}")
    
    if task['updated_at'] != task['created_at']:
        details.append(f"[bold]Updated:[/bold] {task['updated_at']}")
    
    if task['completed_at']:
        details.append(f"[bold]Completed:[/bold] {task['completed_at']}")
    
    panel = Panel('\n'.join(details), title=f"Task #{task_id}", border_style="blue")
    console.print(panel)
    
    # Show dependencies
    if task['dependencies']:
        console.print("\n[bold]Dependencies:[/bold]")
        for dep_id in task['dependencies']:
            dep = db.get_task(dep_id)
            if dep:
                status_icon = '✓' if dep['status'] == 'completed' else '○'
                console.print(f"  {status_icon} #{dep_id}: {dep['title']} [{dep['status']}]")
    
    # Show dependents
    if task['dependents']:
        console.print("\n[bold]Dependent tasks:[/bold]")
        for dep_id in task['dependents']:
            dep = db.get_task(dep_id)
            if dep:
                console.print(f"  • #{dep_id}: {dep['title']} [{dep['status']}]")
    
    # Show affected files
    metadata = task.get('metadata') or {}
    affected_files = metadata.get('affected_files', [])
    if affected_files:
        console.print("\n[bold]Affected files:[/bold]")
        for file in affected_files:
            console.print(f"  • {file}")
    
    # Show notes
    notes = db.get_notes(task_id)
    if notes:
        console.print("\n[bold]Notes:[/bold]")
        for note in notes:
            console.print(f"  • {note['content']}")
            if note['file_ref']:
                console.print(f"    → {note['file_ref']}")
            console.print(f"    [dim]{note['created_at']} by {note['created_by'] or 'Unknown'}[/dim]")


@cli.command()
def blocked():
    """Show all tasks blocked by dependencies."""
    blocked_tasks = db.get_blocked_tasks()
    
    if not blocked_tasks:
        console.print("[green]No blocked tasks![/green]")
        return
    
    console.print("[yellow]Blocked tasks:[/yellow]\n")
    
    for task in blocked_tasks:
        console.print(f"[bold]#{task['id']}:[/bold] {task['title']}")
        console.print(f"  Assignee: {task['assignee'] or 'Unassigned'}")
        console.print("  Blocked by:")
        
        for blocker in task['blocking_tasks']:
            console.print(f"    • #{blocker['id']}: {blocker['title']} [{blocker['status']}]")
        
        console.print()


@cli.command()
@click.argument('task_id', type=int)
@click.argument('depends_on_ids', type=int, nargs=-1, required=True)
def depend(task_id, depends_on_ids):
    """Add dependencies to a task."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]✗[/red] Task #{task_id} not found")
        return
    
    added = []
    for dep_id in depends_on_ids:
        dep = db.get_task(dep_id)
        if not dep:
            console.print(f"[yellow]⚠[/yellow] Task #{dep_id} not found, skipping")
            continue
        
        db.add_dependency(task_id, dep_id)
        added.append(f"#{dep_id}")
    
    if added:
        console.print(f"[green]✓[/green] Added dependencies: {', '.join(added)}")


@cli.command()
@click.argument('task_id', type=int)
def deps(task_id):
    """Show dependency graph for a task."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]✗[/red] Task #{task_id} not found")
        return
    
    # Build dependency tree
    tree = Tree(f"#{task_id}: {task['title']}")
    
    # Add upstream dependencies
    if task['dependencies']:
        deps_node = tree.add("[bold]Depends on:[/bold]")
        for dep_id in task['dependencies']:
            dep = db.get_task(dep_id)
            if dep:
                status_icon = '✓' if dep['status'] == 'completed' else '○'
                deps_node.add(f"{status_icon} #{dep_id}: {dep['title']}")
    
    # Add downstream dependents
    if task['dependents']:
        deps_node = tree.add("[bold]Required by:[/bold]")
        for dep_id in task['dependents']:
            dep = db.get_task(dep_id)
            if dep:
                status_icon = '✓' if dep['status'] == 'completed' else '○'
                deps_node.add(f"{status_icon} #{dep_id}: {dep['title']}")
    
    console.print(tree)


@cli.command()
@click.argument('task_id', type=int)
def check(task_id):
    """Check for conflicts with a specific task."""
    conflicts = db.check_conflicts(task_id)
    
    if not conflicts:
        console.print(f"[green]✓[/green] No conflicts found for task #{task_id}")
        return
    
    console.print(f"[yellow]Conflicts for task #{task_id}:[/yellow]\n")
    
    for conflict in conflicts:
        console.print(f"• Affects task #{conflict['affected_task_id']} ({conflict['affected_task_title']})")
        if conflict['type'] == 'file_overlap':
            console.print(f"  Shared files: {', '.join(conflict['details'])}")


@cli.command()
@click.argument('output_file', type=click.Path())
def export(output_file):
    """Export all tasks to JSON file."""
    output_path = Path(output_file)
    db.export_tasks(output_path)
    console.print(f"[green]✓[/green] Exported tasks to {output_file}")


@cli.command()
@click.option('--limit', '-n', type=int, default=10, help='Number of notes to show')
@click.option('--task', '-t', type=int, help='Filter by task ID')
def notes(limit, task):
    """List recent notes."""
    all_notes = db.get_notes(task)
    
    if not all_notes:
        console.print("[dim]No notes found[/dim]")
        return
    
    # Apply limit
    notes_to_show = all_notes[:limit]
    
    console.print(f"[bold]Recent Notes[/bold] (showing {len(notes_to_show)} of {len(all_notes)})\n")
    
    for note in notes_to_show:
        console.print(f"[cyan]#{note['id']}[/cyan] {note['content']}")
        
        details = []
        if note['task_id']:
            task = db.get_task(note['task_id'])
            if task:
                details.append(f"Task #{note['task_id']}: {task['title']}")
        
        if note['file_ref']:
            details.append(f"File: {note['file_ref']}")
        
        if details:
            console.print(f"  → {' | '.join(details)}")
        
        console.print(f"  [dim]{note['created_at']} by {note['created_by'] or 'Unknown'}[/dim]\n")


if __name__ == '__main__':
    cli()
```

```python
"""Database management for task storage."""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
import fcntl
import time
from typing import List, Dict, Optional, Any


class TaskDB:
    """SQLite-based task database with file locking for concurrent access."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection.
        
        Args:
            db_path: Path to database file. Defaults to ~/.task-manager/tasks.db
        """
        if db_path is None:
            db_dir = Path.home() / ".task-manager"
            db_dir.mkdir(exist_ok=True)
            db_path = db_dir / "tasks.db"
        
        self.db_path = db_path
        self.lock_path = db_path.with_suffix('.lock')
        self._init_db()
    
    @contextmanager
    def _lock(self):
        """Acquire exclusive lock for database operations."""
        lock_file = open(self.lock_path, 'w')
        max_retries = 10
        retry_delay = 0.1
        
        for i in range(max_retries):
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except IOError:
                if i == max_retries - 1:
                    raise RuntimeError("Could not acquire database lock")
                time.sleep(retry_delay)
        
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Tasks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority TEXT DEFAULT 'medium',
                    assignee TEXT,
                    worktree TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    parent_id INTEGER,
                    metadata TEXT,
                    FOREIGN KEY (parent_id) REFERENCES tasks(id)
                )
            """)
            
            # Dependencies table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dependencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    depends_on_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks(id),
                    FOREIGN KEY (depends_on_id) REFERENCES tasks(id),
                    UNIQUE(task_id, depends_on_id)
                )
            """)
            
            # Notes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    content TEXT NOT NULL,
                    file_ref TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            """)
            
            # Conflicts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    affected_task_id INTEGER NOT NULL,
                    description TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks(id),
                    FOREIGN KEY (affected_task_id) REFERENCES tasks(id)
                )
            """)
            
            conn.commit()
            conn.close()
    
    def create_task(self, title: str, description: str = None, 
                   priority: str = 'medium', assignee: str = None,
                   worktree: str = None, parent_id: int = None,
                   metadata: Dict[str, Any] = None) -> int:
        """Create a new task."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            metadata_json = json.dumps(metadata) if metadata else None
            
            cursor.execute("""
                INSERT INTO tasks (title, description, priority, assignee, 
                                 worktree, parent_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (title, description, priority, assignee, worktree, 
                  parent_id, metadata_json))
            
            task_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return task_id
    
    def add_dependency(self, task_id: int, depends_on_id: int):
        """Add a dependency between tasks."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO dependencies (task_id, depends_on_id)
                    VALUES (?, ?)
                """, (task_id, depends_on_id))
                conn.commit()
            except sqlite3.IntegrityError:
                # Dependency already exists
                pass
            finally:
                conn.close()
    
    def update_task(self, task_id: int, **kwargs):
        """Update task fields."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build update query
            fields = []
            values = []
            
            for field, value in kwargs.items():
                if field == 'metadata':
                    value = json.dumps(value) if value else None
                fields.append(f"{field} = ?")
                values.append(value)
            
            # Always update timestamp
            fields.append("updated_at = CURRENT_TIMESTAMP")
            
            # Add completed_at if status is changing to completed
            if kwargs.get('status') == 'completed':
                fields.append("completed_at = CURRENT_TIMESTAMP")
            
            values.append(task_id)
            
            query = f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?"
            cursor.execute(query, values)
            
            conn.commit()
            conn.close()
    
    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get a single task by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        
        if row:
            task = dict(row)
            if task['metadata']:
                task['metadata'] = json.loads(task['metadata'])
            
            # Get dependencies
            cursor.execute("""
                SELECT depends_on_id FROM dependencies 
                WHERE task_id = ?
            """, (task_id,))
            task['dependencies'] = [r[0] for r in cursor.fetchall()]
            
            # Get dependent tasks
            cursor.execute("""
                SELECT task_id FROM dependencies 
                WHERE depends_on_id = ?
            """, (task_id,))
            task['dependents'] = [r[0] for r in cursor.fetchall()]
            
            conn.close()
            return task
        
        conn.close()
        return None
    
    def list_tasks(self, status: str = None, assignee: str = None,
                   worktree: str = None, parent_id: int = None) -> List[Dict[str, Any]]:
        """List tasks with optional filters."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if assignee:
            query += " AND assignee = ?"
            params.append(assignee)
        if worktree:
            query += " AND worktree = ?"
            params.append(worktree)
        if parent_id is not None:
            query += " AND parent_id = ?"
            params.append(parent_id)
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        tasks = []
        
        for row in cursor.fetchall():
            task = dict(row)
            if task['metadata']:
                task['metadata'] = json.loads(task['metadata'])
            tasks.append(task)
        
        conn.close()
        return tasks
    
    def get_blocked_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks blocked by incomplete dependencies."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT t.*
            FROM tasks t
            JOIN dependencies d ON t.id = d.task_id
            JOIN tasks dep ON d.depends_on_id = dep.id
            WHERE t.status = 'pending' 
            AND dep.status != 'completed'
            ORDER BY t.created_at
        """)
        
        tasks = []
        for row in cursor.fetchall():
            task = dict(row)
            if task['metadata']:
                task['metadata'] = json.loads(task['metadata'])
            
            # Get blocking tasks
            cursor.execute("""
                SELECT dep.id, dep.title, dep.status
                FROM dependencies d
                JOIN tasks dep ON d.depends_on_id = dep.id
                WHERE d.task_id = ? AND dep.status != 'completed'
            """, (task['id'],))
            
            task['blocking_tasks'] = [dict(r) for r in cursor.fetchall()]
            tasks.append(task)
        
        conn.close()
        return tasks
    
    def add_note(self, content: str, task_id: int = None, 
                 file_ref: str = None, created_by: str = None):
        """Add a note, optionally attached to a task."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO notes (task_id, content, file_ref, created_by)
                VALUES (?, ?, ?, ?)
            """, (task_id, content, file_ref, created_by))
            
            note_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return note_id
    
    def get_notes(self, task_id: int = None) -> List[Dict[str, Any]]:
        """Get notes, optionally filtered by task."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if task_id:
            cursor.execute("""
                SELECT * FROM notes WHERE task_id = ? 
                ORDER BY created_at DESC
            """, (task_id,))
        else:
            cursor.execute("""
                SELECT * FROM notes ORDER BY created_at DESC
            """)
        
        notes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return notes
    
    def check_conflicts(self, completed_task_id: int) -> List[Dict[str, Any]]:
        """Check for potential conflicts with other tasks."""
        task = self.get_task(completed_task_id)
        if not task:
            return []
        
        conflicts = []
        
        # Get all pending/in-progress tasks
        active_tasks = self.list_tasks(status='pending') + \
                      self.list_tasks(status='in-progress')
        
        # Check for potential conflicts based on metadata
        task_metadata = task.get('metadata') or {}
        affected_files = task_metadata.get('affected_files', [])
        
        for other_task in active_tasks:
            if other_task['id'] == completed_task_id:
                continue
            
            other_metadata = other_task.get('metadata', {})
            other_files = other_metadata.get('affected_files', [])
            
            # Check for file overlap
            if affected_files and other_files:
                overlap = set(affected_files) & set(other_files)
                if overlap:
                    conflicts.append({
                        'task_id': completed_task_id,
                        'affected_task_id': other_task['id'],
                        'affected_task_title': other_task['title'],
                        'type': 'file_overlap',
                        'details': list(overlap)
                    })
        
        # Record conflicts in database
        if conflicts:
            with self._lock():
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for conflict in conflicts:
                    cursor.execute("""
                        INSERT INTO conflicts (task_id, affected_task_id, description)
                        VALUES (?, ?, ?)
                    """, (conflict['task_id'], conflict['affected_task_id'],
                         json.dumps(conflict)))
                
                conn.commit()
                conn.close()
        
        return conflicts
    
    def export_tasks(self, output_file: Path):
        """Export all tasks to JSON."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        data = {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'tasks': [],
            'dependencies': [],
            'notes': []
        }
        
        # Export tasks
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks")
        for row in cursor.fetchall():
            task = dict(row)
            if task['metadata']:
                task['metadata'] = json.loads(task['metadata'])
            data['tasks'].append(task)
        
        # Export dependencies
        cursor.execute("SELECT * FROM dependencies")
        data['dependencies'] = [dict(row) for row in cursor.fetchall()]
        
        # Export notes
        cursor.execute("SELECT * FROM notes")
        data['notes'] = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
```

```python
"""Database management for task storage."""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
import fcntl
import time
from typing import List, Dict, Optional, Any


class TaskDB:
    """SQLite-based task database with file locking for concurrent access."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection.
        
        Args:
            db_path: Path to database file. Defaults to ~/.task-manager/tasks.db
        """
        if db_path is None:
            db_dir = Path.home() / ".task-manager"
            db_dir.mkdir(exist_ok=True)
            db_path = db_dir / "tasks.db"
        
        self.db_path = db_path
        self.lock_path = db_path.with_suffix('.lock')
        self._init_db()
    
    @contextmanager
    def _lock(self):
        """Acquire exclusive lock for database operations."""
        lock_file = open(self.lock_path, 'w')
        max_retries = 10
        retry_delay = 0.1
        
        for i in range(max_retries):
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except IOError:
                if i == max_retries - 1:
                    raise RuntimeError("Could not acquire database lock")
                time.sleep(retry_delay)
        
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Tasks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority TEXT DEFAULT 'medium',
                    assignee TEXT,
                    worktree TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    parent_id INTEGER,
                    metadata TEXT,
                    FOREIGN KEY (parent_id) REFERENCES tasks(id)
                )
            """)
            
            # Dependencies table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dependencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    depends_on_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks(id),
                    FOREIGN KEY (depends_on_id) REFERENCES tasks(id),
                    UNIQUE(task_id, depends_on_id)
                )
            """)
            
            # Notes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    content TEXT NOT NULL,
                    file_ref TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            """)
            
            # Conflicts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    affected_task_id INTEGER NOT NULL,
                    description TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks(id),
                    FOREIGN KEY (affected_task_id) REFERENCES tasks(id)
                )
            """)
            
            conn.commit()
            conn.close()
    
    def create_task(self, title: str, description: str = None, 
                   priority: str = 'medium', assignee: str = None,
                   worktree: str = None, parent_id: int = None,
                   metadata: Dict[str, Any] = None) -> int:
        """Create a new task."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            metadata_json = json.dumps(metadata) if metadata else None
            
            cursor.execute("""
                INSERT INTO tasks (title, description, priority, assignee, 
                                 worktree, parent_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (title, description, priority, assignee, worktree, 
                  parent_id, metadata_json))
            
            task_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return task_id
    
    def add_dependency(self, task_id: int, depends_on_id: int):
        """Add a dependency between tasks."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO dependencies (task_id, depends_on_id)
                    VALUES (?, ?)
                """, (task_id, depends_on_id))
                conn.commit()
            except sqlite3.IntegrityError:
                # Dependency already exists
                pass
            finally:
                conn.close()
    
    def update_task(self, task_id: int, **kwargs):
        """Update task fields."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build update query
            fields = []
            values = []
            
            for field, value in kwargs.items():
                if field == 'metadata':
                    value = json.dumps(value) if value else None
                fields.append(f"{field} = ?")
                values.append(value)
            
            # Always update timestamp
            fields.append("updated_at = CURRENT_TIMESTAMP")
            
            # Add completed_at if status is changing to completed
            if kwargs.get('status') == 'completed':
                fields.append("completed_at = CURRENT_TIMESTAMP")
            
            values.append(task_id)
            
            query = f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?"
            cursor.execute(query, values)
            
            conn.commit()
            conn.close()
    
    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get a single task by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        
        if row:
            task = dict(row)
            if task['metadata']:
                task['metadata'] = json.loads(task['metadata'])
            
            # Get dependencies
            cursor.execute("""
                SELECT depends_on_id FROM dependencies 
                WHERE task_id = ?
            """, (task_id,))
            task['dependencies'] = [r[0] for r in cursor.fetchall()]
            
            # Get dependent tasks
            cursor.execute("""
                SELECT task_id FROM dependencies 
                WHERE depends_on_id = ?
            """, (task_id,))
            task['dependents'] = [r[0] for r in cursor.fetchall()]
            
            conn.close()
            return task
        
        conn.close()
        return None
    
    def list_tasks(self, status: str = None, assignee: str = None,
                   worktree: str = None, parent_id: int = None) -> List[Dict[str, Any]]:
        """List tasks with optional filters."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if assignee:
            query += " AND assignee = ?"
            params.append(assignee)
        if worktree:
            query += " AND worktree = ?"
            params.append(worktree)
        if parent_id is not None:
            query += " AND parent_id = ?"
            params.append(parent_id)
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        tasks = []
        
        for row in cursor.fetchall():
            task = dict(row)
            if task['metadata']:
                task['metadata'] = json.loads(task['metadata'])
            tasks.append(task)
        
        conn.close()
        return tasks
    
    def get_blocked_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks blocked by incomplete dependencies."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT t.*
            FROM tasks t
            JOIN dependencies d ON t.id = d.task_id
            JOIN tasks dep ON d.depends_on_id = dep.id
            WHERE t.status = 'pending' 
            AND dep.status != 'completed'
            ORDER BY t.created_at
        """)
        
        tasks = []
        for row in cursor.fetchall():
            task = dict(row)
            if task['metadata']:
                task['metadata'] = json.loads(task['metadata'])
            
            # Get blocking tasks
            cursor.execute("""
                SELECT dep.id, dep.title, dep.status
                FROM dependencies d
                JOIN tasks dep ON d.depends_on_id = dep.id
                WHERE d.task_id = ? AND dep.status != 'completed'
            """, (task['id'],))
            
            task['blocking_tasks'] = [dict(r) for r in cursor.fetchall()]
            tasks.append(task)
        
        conn.close()
        return tasks
    
    def add_note(self, content: str, task_id: int = None, 
                 file_ref: str = None, created_by: str = None):
        """Add a note, optionally attached to a task."""
        with self._lock():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO notes (task_id, content, file_ref, created_by)
                VALUES (?, ?, ?, ?)
            """, (task_id, content, file_ref, created_by))
            
            note_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return note_id
    
    def get_notes(self, task_id: int = None) -> List[Dict[str, Any]]:
        """Get notes, optionally filtered by task."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if task_id:
            cursor.execute("""
                SELECT * FROM notes WHERE task_id = ? 
                ORDER BY created_at DESC
            """, (task_id,))
        else:
            cursor.execute("""
                SELECT * FROM notes ORDER BY created_at DESC
            """)
        
        notes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return notes
    
    def check_conflicts(self, completed_task_id: int) -> List[Dict[str, Any]]:
        """Check for potential conflicts with other tasks."""
        task = self.get_task(completed_task_id)
        if not task:
            return []
        
        conflicts = []
        
        # Get all pending/in-progress tasks
        active_tasks = self.list_tasks(status='pending') + \
                      self.list_tasks(status='in-progress')
        
        # Check for potential conflicts based on metadata
        task_metadata = task.get('metadata') or {}
        affected_files = task_metadata.get('affected_files', [])
        
        for other_task in active_tasks:
            if other_task['id'] == completed_task_id:
                continue
            
            other_metadata = other_task.get('metadata') or {}
            other_files = other_metadata.get('affected_files', [])
            
            # Check for file overlap
            if affected_files and other_files:
                overlap = set(affected_files) & set(other_files)
                if overlap:
                    conflicts.append({
                        'task_id': completed_task_id,
                        'affected_task_id': other_task['id'],
                        'affected_task_title': other_task['title'],
                        'type': 'file_overlap',
                        'details': list(overlap)
                    })
        
        # Record conflicts in database
        if conflicts:
            with self._lock():
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for conflict in conflicts:
                    cursor.execute("""
                        INSERT INTO conflicts (task_id, affected_task_id, description)
                        VALUES (?, ?, ?)
                    """, (conflict['task_id'], conflict['affected_task_id'],
                         json.dumps(conflict)))
                
                conn.commit()
                conn.close()
        
        return conflicts
    
    def export_tasks(self, output_file: Path):
        """Export all tasks to JSON."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        data = {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'tasks': [],
            'dependencies': [],
            'notes': []
        }
        
        # Export tasks
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks")
        for row in cursor.fetchall():
            task = dict(row)
            if task['metadata']:
                task['metadata'] = json.loads(task['metadata'])
            data['tasks'].append(task)
        
        # Export dependencies
        cursor.execute("SELECT * FROM dependencies")
        data['dependencies'] = [dict(row) for row in cursor.fetchall()]
        
        # Export notes
        cursor.execute("SELECT * FROM notes")
        data['notes'] = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
```

Now let me create a convenience script for using the `tm` command more easily:

```plaintext
#!/usr/bin/env python3
"""Convenience wrapper for task manager CLI."""

import sys
from task_manager.cli import cli

if __name__ == '__main__':
    cli()
```

Let me create an example script demonstrating advanced usage scenarios:

```shellscript
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
```

Let me update the README with more comprehensive documentation:

```markdown
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
```

Let me test the `tm` script directly:

Let me create a setup script for easy installation:

```shellscript
#!/bin/bash
# Setup script for Task Manager

echo "Task Manager Setup"
echo "=================="
echo

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found."
    exit 1
fi

# Install the package
echo "Installing task-manager package..."
pip3 install -e . || {
    echo "Error: Failed to install package. You may need to use 'sudo' or install in user mode."
    exit 1
}

# Make the tm script executable
chmod +x tm

# Determine the best location for the tm command
if [ -d "$HOME/.local/bin" ]; then
    BIN_DIR="$HOME/.local/bin"
elif [ -d "$HOME/bin" ]; then
    BIN_DIR="$HOME/bin"
else
    echo
    echo "Creating $HOME/.local/bin for user scripts..."
    mkdir -p "$HOME/.local/bin"
    BIN_DIR="$HOME/.local/bin"
fi

# Create a symlink to the tm script
echo "Creating symlink in $BIN_DIR..."
ln -sf "$(pwd)/tm" "$BIN_DIR/tm"

# Check if BIN_DIR is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo
    echo "Note: $BIN_DIR is not in your PATH."
    echo "Add this line to your shell configuration file (~/.bashrc, ~/.zshrc, etc.):"
    echo
    echo "  export PATH=\"\$PATH:$BIN_DIR\""
    echo
    echo "Then reload your shell or run: source ~/.bashrc"
else
    echo "✓ $BIN_DIR is already in your PATH"
fi

echo
echo "Setup complete! You can now use the 'tm' command."
echo
echo "Quick test:"
echo "  tm --version"
echo "  tm --help"
echo
echo "Create your first task:"
echo "  tm create \"My first task\" --priority high"
```

Let me create a final demonstration of the tool working:

## Summary

I've successfully created a comprehensive task manager tool designed specifically for AI agents working in parallel across different git worktrees. Here's what was built:

### Core Features Implemented:

1. **Task Management**
   - Create tasks with titles, descriptions, priorities, and assignees
   - Support for subtasks with parent-child relationships
   - Task dependencies that block execution until prerequisites are complete
   - Multiple task states: pending, in-progress, completed, cancelled

2. **Collaboration Features**
   - Agent identification system (via TM_AGENT_ID or user@hostname)
   - Cross-worktree task visibility through centralized SQLite database
   - File-based locking for safe concurrent access
   - Conflict detection when tasks affect the same files

3. **Unix-Style CLI**
   - Clean command structure: `tm [command] [args] [options]`
   - Rich terminal output with tables and tree views
   - Intuitive shortcuts (e.g., `--assignee me`)
   - Comprehensive help system

4. **Advanced Features**
   - File reference tracking with line numbers
   - Quick notes and TODOs attached to tasks or standalone
   - Dependency visualization and blocked task detection
   - JSON export for backup and migration
   - Git-aware with automatic worktree detection

### Project Structure:
```
task-manager/
├── README.md           # Comprehensive documentation
├── setup.py            # Python package configuration
├── setup.sh            # Installation helper script
├── examples.sh         # Usage examples
├── test_tm.py          # Test suite
├── tm                  # Executable wrapper
└── task_manager/       # Main package
    ├── __init__.py
    ├── cli.py          # Click-based CLI interface
    ├── database.py     # SQLite storage with locking
    └── utils.py        # Helper functions
```

### Key Design Decisions:

1. **SQLite Database**: Provides ACID compliance and handles concurrent access well
2. **File Locking**: Ensures data integrity across parallel agents
3. **Click Framework**: Creates a professional Unix-style interface
4. **Rich Library**: Beautiful terminal output with tables and trees
5. **Centralized Storage**: ~/.task-manager/tasks.db allows cross-worktree access

### Usage Example:
```bash
# Install
cd task-manager && pip3 install -e .

# Create tasks
./tm create "Implement feature X" --priority high
./tm create "Design API" --parent 1 --assignee agent-1
./tm create "Write tests" --parent 1 --depends-on 2

# Check status
./tm list --tree
./tm blocked
./tm show 1

# Complete work
./tm complete 2
```

The tool successfully addresses all the requirements:
- ✅ Supports parallel agent workflows
- ✅ Handles task dependencies and blocking
- ✅ Allows quick notes with file references
- ✅ Detects conflicts when tasks are completed
- ✅ Provides a clean Unix-style interface
- ✅ Works across different git worktrees

The task manager is now ready for use by AI agents to coordinate their parallel work effectively!

```plaintext
task-manager/
├── README.md           # Comprehensive documentation
├── setup.py            # Python package configuration
├── setup.sh            # Installation helper script
├── examples.sh         # Usage examples
├── test_tm.py          # Test suite
├── tm                  # Executable wrapper
└── task_manager/       # Main package
    ├── __init__.py
    ├── cli.py          # Click-based CLI interface
    ├── database.py     # SQLite storage with locking
    └── utils.py        # Helper functions
```

```shellscript
# Install
cd task-manager && pip3 install -e .

# Create tasks
./tm create "Implement feature X" --priority high
./tm create "Design API" --parent 1 --assignee agent-1
./tm create "Write tests" --parent 1 --depends-on 2

# Check status
./tm list --tree
./tm blocked
./tm show 1

# Complete work
./tm complete 2
```

