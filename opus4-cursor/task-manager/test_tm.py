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