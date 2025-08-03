import sys
import os
import pytest
from typer.testing import CliRunner

# Add the project root to the PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app, load_tasks, save_tasks
from models import Task, TaskStatus
import json

runner = CliRunner()

@pytest.fixture
def temp_tasks_file(tmp_path):
    temp_file = tmp_path / "tasks.json"
    temp_file.touch()
    return temp_file

@pytest.fixture(autouse=True)
def setup_teardown(monkeypatch, temp_tasks_file):
    monkeypatch.setattr("main.TASKS_FILE", str(temp_tasks_file))
    # Setup: ensure tasks.json is empty before each test
    save_tasks([])
    yield
    # Teardown: clean up tasks.json after each test
    save_tasks([])

def test_create_task():
    result = runner.invoke(app, ["create", "Test Task 1"])
    assert result.exit_code == 0
    assert "Created task" in result.stdout
    tasks = load_tasks()
    assert len(tasks) == 1
    assert tasks[0].title == "Test Task 1"
    assert tasks[0].status == TaskStatus.OPEN

def test_create_task_with_dependency():
    result1 = runner.invoke(app, ["create", "Task 1"])
    task1_id = load_tasks()[0].id
    result2 = runner.invoke(app, ["create", "Task 2", "--dependency", task1_id])
    assert result2.exit_code == 0
    tasks = load_tasks()
    assert len(tasks) == 2
    assert tasks[1].title == "Task 2"
    assert tasks[1].status == TaskStatus.BLOCKED
    assert tasks[1].dependencies == [task1_id]

def test_list_tasks_empty():
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "ID" in result.stdout # Check for header

def test_list_tasks_with_tasks():
    runner.invoke(app, ["create", "Test Task 1"])
    runner.invoke(app, ["create", "Test Task 2"])
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Test Task 1" in result.stdout
    assert "Test Task 2" in result.stdout

def test_update_task():
    runner.invoke(app, ["create", "Test Task 1"])
    task_id = load_tasks()[0].id
    result = runner.invoke(app, ["update", task_id, "--title", "Updated Title"])
    assert result.exit_code == 0
    assert "Updated task" in result.stdout
    tasks = load_tasks()
    assert tasks[0].title == "Updated Title"

def test_update_task_not_found():
    result = runner.invoke(app, ["update", "nonexistent-id", "--title", "Wont work"])
    assert result.exit_code == 1
    assert "not found" in result.stdout

def test_done_task():
    runner.invoke(app, ["create", "Task 1"])
    task1_id = load_tasks()[0].id
    runner.invoke(app, ["create", "Task 2", "--dependency", task1_id])
    
    result = runner.invoke(app, ["done", task1_id])
    assert result.exit_code == 0
    assert "Completed task" in result.stdout
    assert "Unblocked task" in result.stdout
    
    tasks = load_tasks()
    assert tasks[0].status == TaskStatus.DONE
    assert tasks[1].status == TaskStatus.OPEN
