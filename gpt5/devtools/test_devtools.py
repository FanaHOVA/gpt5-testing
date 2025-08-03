import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import dev_cli as cli  # noqa


class DevToolsTest(unittest.TestCase):
    def run_cli(self, args):
        f = io.StringIO()
        code = 0
        with redirect_stdout(f):
            try:
                cli.main(args)
            except SystemExit as e:
                code = int(e.code)
        return f.getvalue(), code

    def test_doctor_json(self):
        out, code = self.run_cli(["doctor", "--json"])
        self.assertIn("\"checks\"", out)
        data = json.loads(out)
        self.assertIn("sys", data)
        self.assertIsInstance(data["checks"], list)

    def test_code_map_build_and_find(self):
        repo = Path(os.environ.get("TEST_REPO_ROOT", str(Path(__file__).resolve().parents[1])))
        out, code = self.run_cli(["code-map", "build", "--root", str(repo)])
        self.assertEqual(code, 0)
        path = Path(out.strip())
        self.assertTrue(path.exists())
        # find a known symbol
        out, code = self.run_cli(["code-map", "find", "--map", str(path), "--kind", "symbol", "--query", "build_parser", "--limit", "5"])
        self.assertEqual(code, 0)
        self.assertIn("task-manager/cli.py", out)

    def test_csearch_symbol_and_text(self):
        repo = Path(os.environ.get("TEST_REPO_ROOT", str(Path(__file__).resolve().parents[1])))
        # ensure map exists
        out, code = self.run_cli(["code-map", "build", "--root", str(repo)])
        self.assertEqual(code, 0)
        # symbol search
        out, code = self.run_cli(["csearch", "--kind", "symbol", "--query", "build_parser"]) 
        self.assertEqual(code, 0)
        self.assertIn("task-manager/cli.py", out)
        # text fallback: search for a known token in this file
        out, code = self.run_cli(["csearch", "--kind", "text", "--query", "Developer tools"]) 
        self.assertEqual(code, 0)

    def test_e2e_scaffold_and_preflight(self):
        # scaffold an e2e spec and run preflight without failing
        out, code = self.run_cli(["e2e", "scaffold", "smoke", "--url", "https://example.com"])
        self.assertEqual(code, 0)
        path = Path(out.strip())
        self.assertTrue((path / "spec.py").exists())
        # run e2e via the CLI runner (uses stub if playwright not installed)
        out, code = self.run_cli(["e2e", "run", "smoke"]) 
        self.assertEqual(code, 0)
        # preflight quick mode: avoids running nested test discovery
        out, code = self.run_cli(["preflight", "--e2e", "smoke", "--quick"]) 
        # Assert it produced the summary heading
        self.assertIn("PRE-FLIGHT SUMMARY", out)

    def test_flake_runner(self):
        # run flake on a known passing tiny suite
        root = Path(__file__).resolve().parent / "testdata" / "flake_ok"
        out, code = self.run_cli(["flake", "--start", str(root), "--pattern", "test_*.py", "--runs", "2", "--seed", "1"])
        self.assertIn("failures=0", out)
        self.assertEqual(code, 0)

    def test_codemod_plan_apply_and_trace_and_runbook(self):
        import tempfile
        import sqlite3
        # codemod on a temp tree
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.py"
            p.write_text("foo = 1\nprint('foo')\n", encoding="utf-8")
            out, code = self.run_cli(["codemod", "plan", "--root", tmp, "--regex", "foo", "--replace", "bar", "--limit", "5"])
            self.assertIn("---", out)
            out, code = self.run_cli(["codemod", "apply", "--root", tmp, "--regex", "foo", "--replace", "bar", "--limit", "5", "--yes"])
            self.assertIn("changed_files=1", out)
            self.assertIn("bar", p.read_text())

        # trace simple expr
        with tempfile.TemporaryDirectory() as tmp:
            prof = str(Path(tmp) / "trace.prof")
            out, code = self.run_cli(["trace", "run", "--expr", "sum(range(10000))", "--out", prof])
            self.assertTrue(Path(prof).exists())

        # runbook from a temp DB
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "tasks.db")
            # initialize via task-manager schema
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "task-manager"))
            import db as tdb  # type: ignore
            tdb.ensure_db(Path(db))
            with sqlite3.connect(db) as conn:
                now = "2025-01-01T00:00:00"
                conn.execute("INSERT INTO tasks(title, description, status, assignee, priority, due_date, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)", ("T", "desc", "pending", "", 1, None, now, now))
                tid = conn.execute("SELECT id FROM tasks").fetchone()[0]
                conn.execute("INSERT INTO notes(task_id, content, file, created_at) VALUES (?,?,?,?)", (tid, "note", None, now))
                conn.execute("INSERT INTO resources(task_id, kind, resource, created_at) VALUES (?,?,?,?)", (tid, "touch", "file:/tmp/x", now))
            out, code = self.run_cli(["runbook", "generate", "--task", str(tid), "--db", db, "--out", str(Path(tmp) / "rb.md")])
            self.assertTrue(Path(out.strip()).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
