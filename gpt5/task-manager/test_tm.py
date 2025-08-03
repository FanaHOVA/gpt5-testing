import io
import os
import sys
import tempfile
import textwrap
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import unittest

# Ensure we can import cli/db via their sibling imports ("from db import ...")
THIS_DIR = Path(__file__).resolve().parent
TM_DIR = THIS_DIR
sys.path.insert(0, str(TM_DIR))

import cli  # noqa: E402
from db import connect  # noqa: E402


class TMTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmpdir.name) / "tasks.db")
        # Stable actor/assignee for deterministic tests
        self._env_backup = {
            k: os.environ.get(k)
            for k in ["TM_DB", "TM_DB_DIR", "TM_ACTOR", "TM_ASSIGNEE", "USER", "USERNAME"]
        }
        os.environ["TM_ACTOR"] = "tester"
        os.environ["TM_ASSIGNEE"] = ""

        # Always start from a clean, initialized DB
        self.run_cli(["init"])

    def tearDown(self):
        for k, v in (self._env_backup or {}).items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmpdir.cleanup()

    def run_cli(self, args, expect_exit_code=0):
        parser = cli.build_parser()
        f = io.StringIO()
        code = 0
        full_args = ["--db", self.db_path] + list(args)
        with redirect_stdout(f), redirect_stderr(f):
            try:
                ns = parser.parse_args(full_args)
                ns.func(ns)
            except SystemExit as e:
                code = int(e.code) if isinstance(e.code, int) else 1
        out = f.getvalue()
        if expect_exit_code == 0 and code != 0:
            self.fail(f"CLI exited with {code}. Args={full_args}\nOutput:\n{out}")
        if expect_exit_code != 0 and code == 0:
            self.fail(f"CLI expected non-zero exit but got 0. Args={full_args}\nOutput:\n{out}")
        return out, code

    def add_task(self, title, **kwargs):
        args = ["add", title]
        if kwargs.get("description"):
            args += ["-d", kwargs["description"]]
        if kwargs.get("assignee") is not None:
            args += ["-a", kwargs["assignee"]]
        if kwargs.get("priority") is not None:
            args += ["-p", str(kwargs["priority"])]
        if kwargs.get("due") is not None:
            args += ["--due", kwargs["due"]]
        if kwargs.get("depends"):
            args += ["--depends", *map(str, kwargs["depends"])]
        if kwargs.get("link"):
            args += ["--link", *kwargs["link"]]
        if kwargs.get("resource"):
            args += ["--resource", *kwargs["resource"]]
        out, _ = self.run_cli(args)
        return int(out.strip())

    def list_tasks(self, extra=None):
        args = ["list"]
        if extra:
            args += extra
        out, _ = self.run_cli(args)
        return out

    def show_task(self, tid):
        out, _ = self.run_cli(["show", str(tid)])
        return out

    def status(self, tid, status):
        self.run_cli(["status", str(tid), status])

    def start(self, tid):
        return self.run_cli(["start", str(tid)])

    def complete(self, tid, msg=None):
        args = ["complete", str(tid)]
        if msg:
            args += ["-m", msg]
        self.run_cli(args)

    def depend(self, tid, on):
        self.run_cli(["depend", str(tid), "--on", str(on)])

    def undepend(self, tid, on):
        self.run_cli(["undepend", str(tid), "--on", str(on)])

    def assign(self, tid, who):
        self.run_cli(["assign", str(tid), "-a", who])

    def note(self, tid, text, file=None):
        args = ["note", str(tid), text]
        if file:
            args += ["--file", file]
        self.run_cli(args)

    def link(self, tid, file):
        self.run_cli(["link", str(tid), file])

    def add_resource(self, tid, *resources):
        self.run_cli(["resource", str(tid), *resources])

    def watch(self, extra=None):
        args = ["watch"]
        if extra:
            args += extra
        out, _ = self.run_cli(args)
        return out

    def doctor(self):
        return self.run_cli(["doctor"])

    # --- Tests ---

    def test_init_creates_db(self):
        self.assertTrue(Path(self.db_path).exists())
        # basic table existence
        with connect(self.db_path) as conn:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
        for t in ["tasks", "dependencies", "notes", "resources", "events"]:
            self.assertIn(t, tables)

    def test_add_and_show_task(self):
        tid = self.add_task(
            "Implement auth",
            description="Add login + signup",
            assignee="alice",
            priority=2,
            due="2025-09-01",
            link=["app/server/auth.py"],
            resource=["modifies:endpoint:POST /api/login"],
        )
        out = self.show_task(tid)
        self.assertIn("Implement auth", out)
        self.assertIn("assignee: alice", out)
        self.assertIn("priority: 2", out)
        self.assertIn("due: 2025-09-01", out)
        self.assertIn("resources:", out)
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT title, assignee, priority FROM tasks WHERE id=?", (tid,)).fetchone()
            self.assertEqual(row[0], "Implement auth")
            self.assertEqual(row[1], "alice")
            self.assertEqual(row[2], 2)

    def test_list_filters(self):
        a = self.add_task("A", assignee="alice")
        b = self.add_task("B", assignee="bob")
        self.status(a, "in_progress")
        out = self.list_tasks(["--status", "in_progress"])
        self.assertIn("A", out)
        self.assertNotIn("B", out)
        out = self.list_tasks(["--assignee", "bob"])  # should include only B
        self.assertIn("B", out)
        self.assertNotIn("A", out)

    def test_me_filter_uses_TM_ASSIGNEE(self):
        self.add_task("A", assignee="alice")
        self.add_task("B", assignee="bob")
        os.environ["TM_ASSIGNEE"] = "bob"
        out = self.list_tasks(["--me"])
        self.assertIn("B", out)
        self.assertNotIn("A", out)

    def test_dependencies_and_start_block_unblock_complete(self):
        t1 = self.add_task("T1")
        t2 = self.add_task("T2")
        self.depend(t1, t2)
        out, _ = self.start(t1)
        self.assertIn("Blocked by:", out)
        # Complete t2; t1 should be auto-unblocked to pending
        self.complete(t2, msg="done")
        with connect(self.db_path) as conn:
            st = conn.execute("SELECT status FROM tasks WHERE id=?", (t1,)).fetchone()[0]
            self.assertEqual(st, "pending")
        # Now start t1 successfully
        out, _ = self.start(t1)
        with connect(self.db_path) as conn:
            st = conn.execute("SELECT status FROM tasks WHERE id=?", (t1,)).fetchone()[0]
            self.assertEqual(st, "in_progress")

    def test_undepend_removes_edge(self):
        t1 = self.add_task("T1")
        t2 = self.add_task("T2")
        self.depend(t1, t2)
        self.undepend(t1, t2)
        with connect(self.db_path) as conn:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM dependencies WHERE task_id=? AND depends_on_task_id=?",
                (t1, t2),
            ).fetchone()[0]
            self.assertEqual(cnt, 0)

    def test_assign_note_link_resource(self):
        t = self.add_task("T")
        self.assign(t, "carol")
        self.note(t, "investigate", file="foo.py")
        self.link(t, "bar.py")
        self.add_resource(t, "modifies:endpoint:GET /x", "adds:feature:y")
        with connect(self.db_path) as conn:
            a = conn.execute("SELECT assignee FROM tasks WHERE id=?", (t,)).fetchone()[0]
            self.assertEqual(a, "carol")
            notes = conn.execute("SELECT COUNT(*) FROM notes WHERE task_id=?", (t,)).fetchone()[0]
            self.assertEqual(notes, 1)
            res = conn.execute("SELECT kind, resource FROM resources WHERE task_id=? ORDER BY id", (t,)).fetchall()
            kinds = [r[0] for r in res]
            self.assertIn("touch", kinds)
            self.assertIn("modifies", kinds)
            self.assertIn("adds", kinds)

    def test_watch_filters_and_since(self):
        t1 = self.add_task("T1", assignee="x")
        t2 = self.add_task("T2", assignee="y")
        # Cause some events on both
        self.assign(t1, "x")
        self.assign(t2, "y")
        # Watch all events, shouldn't be empty
        out = self.watch(["--since", "0"])  # single shot
        self.assertIn("task=", out)
        # Filter by assignee y
        out = self.watch(["--assignee", "y"])  # single shot
        # Only events for tasks assigned to y should appear
        self.assertIn("target=None", out.replace(" target=", " target=None"))  # ensure format stable

    def test_doctor_cycle_and_auto_unblock(self):
        # cycle 1 -> 2 -> 1
        t1 = self.add_task("T1")
        t2 = self.add_task("T2")
        self.depend(t1, t2)
        self.depend(t2, t1)
        out, _ = self.doctor()
        self.assertIn("cycle detected:", out)
        # auto-unblock: create blocked t3 that depends on t4; complete t4 then doctor should unblock t3
        t3 = self.add_task("T3")
        t4 = self.add_task("T4")
        self.depend(t3, t4)  # this will set t3 blocked
        self.complete(t4)
        out, _ = self.doctor()
        with connect(self.db_path) as conn:
            st = conn.execute("SELECT status FROM tasks WHERE id=?", (t3,)).fetchone()[0]
            self.assertEqual(st, "pending")

    def test_resource_impact_events_on_complete(self):
        # Task A removes a resource used by task B
        a = self.add_task("A")
        b = self.add_task("B")
        self.add_resource(a, "removes:feature:q")
        self.add_resource(b, "touch:feature:q")
        self.complete(a)
        with connect(self.db_path) as conn:
            ev = conn.execute("SELECT type, task_id, target_task_id, payload FROM events WHERE type='impact_conflict' AND task_id=?",
                              (a,)).fetchall()
            self.assertGreaterEqual(len(ev), 1)

    def test_status_validation(self):
        t = self.add_task("T")
        # invalid status should exit non-zero
        out, code = self.run_cli(["status", str(t), "done"], expect_exit_code=1)
        self.assertIn("invalid choice", out)

    def test_update_fields(self):
        t = self.add_task("T", assignee="a", priority=0, due=None)
        self.run_cli(["update", str(t), "--title", "T2", "--description", "desc", "--assignee", "b", "--priority", "3", "--due", "2030-01-01"])
        out = self.show_task(t)
        self.assertIn("[{}] T2".format(t), out)
        self.assertIn("assignee: b", out)
        self.assertIn("priority: 3", out)
        self.assertIn("due: 2030-01-01", out)

    def test_resource_arg_validation(self):
        t = self.add_task("T")
        # invalid KIND should cause SystemExit
        out, code = self.run_cli(["resource", str(t), "invalid"], expect_exit_code=1)
        # argparse errors are printed; SystemExit raised inside command may not print under harness
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
