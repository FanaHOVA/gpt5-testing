import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_DIR = Path(os.environ.get("TM_DB_DIR", os.path.expanduser("~/.gpt5")))
DEFAULT_DB_PATH = Path(os.environ.get("TM_DB", str(DEFAULT_DB_DIR / "tasks.db")))

SCHEMA = r"""
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','blocked','completed','cancelled')),
  assignee TEXT,
  priority INTEGER NOT NULL DEFAULT 0,
  due_date TEXT,
  blocked_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dependencies (
  task_id INTEGER NOT NULL,
  depends_on_task_id INTEGER NOT NULL,
  PRIMARY KEY (task_id, depends_on_task_id),
  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
  FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS notes (
  id INTEGER PRIMARY KEY,
  task_id INTEGER NOT NULL,
  content TEXT NOT NULL,
  file TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS resources (
  id INTEGER PRIMARY KEY,
  task_id INTEGER NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('touch','adds','removes','modifies','depends')),
  resource TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL,
  actor TEXT,
  type TEXT NOT NULL,
  task_id INTEGER,
  target_task_id INTEGER,
  payload TEXT,
  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL,
  FOREIGN KEY (target_task_id) REFERENCES tasks(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee);
CREATE INDEX IF NOT EXISTS idx_deps_task ON dependencies(task_id);
CREATE INDEX IF NOT EXISTS idx_deps_depends ON dependencies(depends_on_task_id);
CREATE INDEX IF NOT EXISTS idx_resources_task ON resources(task_id);
CREATE INDEX IF NOT EXISTS idx_resources_res ON resources(resource);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
"""


from typing import Optional

def ensure_db(path: Optional[Path] = None) -> Path:
    db_path = Path(path) if path else DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
    return db_path


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


@contextmanager
def connect(db_path: Optional[Path] = None):
    p = Path(db_path) if db_path else DEFAULT_DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, timeout=30, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        yield conn
    finally:
        conn.close()


from typing import Dict

def dict_row(row: sqlite3.Row) -> Dict:
    return {k: row[k] for k in row.keys()}
