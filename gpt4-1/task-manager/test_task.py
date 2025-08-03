import os
import json
import tempfile
import pytest
from datetime import datetime, timedelta
from task import Task, load_tasks, save_tasks, TASKS_FILE

@pytest.fixture
def sample_task():
    return Task(
        id=1,
        description="Test task",
        status="todo",
        assignee="alice",
        file="file.py",
        line=42,
        dependencies=[2, 3],
        dependents=[4],
        notifications=["bob@example.com"],
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T01:00:00"
    )

@pytest.fixture
def minimal_task():
    return Task(id=2, description="Minimal task")

def test_task_creation_defaults(minimal_task):
    t = minimal_task
    assert t.status == "todo"
    assert t.assignee is None
    assert t.file is None
    assert t.line is None
    assert t.dependencies == []
    assert t.dependents == []
    assert t.notifications == []
    # created_at and updated_at should be close to now
    now = datetime.utcnow()
    created = datetime.fromisoformat(t.created_at)
    updated = datetime.fromisoformat(t.updated_at)
    assert abs((now - created).total_seconds()) < 10
    assert abs((now - updated).total_seconds()) < 10

def test_task_creation_full(sample_task):
    t = sample_task
    assert t.id == 1
    assert t.description == "Test task"
    assert t.status == "todo"
    assert t.assignee == "alice"
    assert t.file == "file.py"
    assert t.line == 42
    assert t.dependencies == [2, 3]
    assert t.dependents == [4]
    assert t.notifications == ["bob@example.com"]
    assert t.created_at == "2023-01-01T00:00:00"
    assert t.updated_at == "2023-01-01T01:00:00"

def test_to_dict_and_from_dict(sample_task):
    d = sample_task.to_dict()
    t2 = Task.from_dict(d)
    assert t2.to_dict() == d

def test_dependencies_and_dependents():
    t = Task(id=3, description="Deps", dependencies=[1], dependents=[2])
    assert t.dependencies == [1]
    assert t.dependents == [2]
    # Add a dependency
    t.dependencies.append(4)
    assert 4 in t.dependencies
    # Remove a dependent
    t.dependents.remove(2)
    assert t.dependents == []

def test_notifications():
    t = Task(id=4, description="Notify", notifications=["a@b.com"])
    assert t.notifications == ["a@b.com"]
    t.notifications.append("c@d.com")
    assert "c@d.com" in t.notifications

def test_persistence(monkeypatch, tmp_path, sample_task, minimal_task):
    # Patch TASKS_FILE to a temp file
    test_file = tmp_path / "tasks.json"
    monkeypatch.setattr("task.TASKS_FILE", str(test_file))
    # Save tasks
    save_tasks([sample_task, minimal_task])
    assert test_file.exists()
    # Load tasks
    loaded = load_tasks()
    assert len(loaded) == 2
    assert loaded[0].to_dict() == sample_task.to_dict()
    assert loaded[1].to_dict()["description"] == "Minimal task"

def test_load_tasks_empty(monkeypatch, tmp_path):
    test_file = tmp_path / "empty.json"
    monkeypatch.setattr("task.TASKS_FILE", str(test_file))
    # File does not exist
    tasks = load_tasks()
    assert tasks == []
    # File exists but is empty/invalid
    test_file.write_text("")
    tasks = load_tasks()
    assert tasks == []
    test_file.write_text("not json")
    tasks = load_tasks()
    assert tasks == []

def test_save_tasks_creates_file(monkeypatch, tmp_path, minimal_task):
    test_file = tmp_path / "tasks.json"
    monkeypatch.setattr("task.TASKS_FILE", str(test_file))
    save_tasks([minimal_task])
    assert test_file.exists()
    with open(test_file) as f:
        data = json.load(f)
    assert data[0]["description"] == "Minimal task"