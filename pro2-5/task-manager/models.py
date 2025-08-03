from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
import uuid

class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"

class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.OPEN
    assignee: Optional[str] = None
    dependencies: List[str] = []
    file_path: Optional[str] = None
