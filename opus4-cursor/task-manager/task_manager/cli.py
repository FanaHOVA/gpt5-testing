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