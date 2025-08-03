import json
import os
from typing import List, Optional, Dict, Any
from datetime import datetime

TASKS_FILE = os.path.join(os.path.dirname(__file__), 'tasks.json')

class Task:
    def __init__(self, 
                 id: int,
                 description: str,
                 status: str = 'todo',
                 assignee: Optional[str] = None,
                 file: Optional[str] = None,
                 line: Optional[int] = None,
                 dependencies: Optional[List[int]] = None,
                 dependents: Optional[List[int]] = None,
                 notifications: Optional[List[str]] = None,
                 created_at: Optional[str] = None,
                 updated_at: Optional[str] = None):
        self.id = id
        self.description = description
        self.status = status
        self.assignee = assignee
        self.file = file
        self.line = line
        self.dependencies = dependencies or []
        self.dependents = dependents or []
        self.notifications = notifications or []
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.updated_at = updated_at or datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'description': self.description,
            'status': self.status,
            'assignee': self.assignee,
            'file': self.file,
            'line': self.line,
            'dependencies': self.dependencies,
            'dependents': self.dependents,
            'notifications': self.notifications,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Task':
        return Task(
            id=data['id'],
            description=data['description'],
            status=data.get('status', 'todo'),
            assignee=data.get('assignee'),
            file=data.get('file'),
            line=data.get('line'),
            dependencies=data.get('dependencies', []),
            dependents=data.get('dependents', []),
            notifications=data.get('notifications', []),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
        )

def load_tasks() -> List[Task]:
    if not os.path.exists(TASKS_FILE):
        return []
    with open(TASKS_FILE, 'r') as f:
        try:
            data = json.load(f)
            return [Task.from_dict(item) for item in data]
        except json.JSONDecodeError:
            return []

def save_tasks(tasks: List[Task]):
    with open(TASKS_FILE, 'w') as f:
        json.dump([task.to_dict() for task in tasks], f, indent=2)
