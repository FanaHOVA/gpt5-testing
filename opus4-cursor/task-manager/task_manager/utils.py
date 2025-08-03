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