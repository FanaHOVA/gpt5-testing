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