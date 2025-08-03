import argparse
import json
import os
import sys
import textwrap
import time
from pathlib import Path

from db import connect, ensure_db, now_iso, dict_row, DEFAULT_DB_PATH

STATUSES = ['pending','in_progress','blocked','completed','cancelled']
RESOURCE_KINDS = ['touch','adds','removes','modifies','depends']


def actor_name() -> str:
    return os.environ.get('TM_ACTOR') or os.environ.get('USER') or os.environ.get('USERNAME') or 'unknown'


def print_table(rows, headers):
    widths = [len(h) for h in headers]
    for r in rows:
        for i, h in enumerate(headers):
            widths[i] = max(widths[i], len(str(r.get(h, ''))))
    fmt = '  '.join('{:' + str(w) + '}' for w in widths)
    print(fmt.format(*headers))
    print('  '.join('-' * w for w in widths))
    for r in rows:
        print(fmt.format(*(str(r.get(h, '')) for h in headers)))


from typing import Optional, List, Dict

def add_event(conn, type_, task_id=None, target_task_id=None, payload: Optional[Dict] = None):
    conn.execute(
        'INSERT INTO events(created_at, actor, type, task_id, target_task_id, payload) VALUES (?,?,?,?,?,?)',
        (now_iso(), actor_name(), type_, task_id, target_task_id, json.dumps(payload or {}))
    )


def init_cmd(args):
    p = Path(args.db) if args.db else DEFAULT_DB_PATH
    ensure_db(p)
    print(f"Initialized database at {p}")


def add_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        now = now_iso()
        cur = conn.execute(
            'INSERT INTO tasks(title, description, status, assignee, priority, due_date, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)',
            (args.title, args.description or '', 'pending', args.assignee, args.priority, args.due, now, now)
        )
        task_id = cur.lastrowid
        add_event(conn, 'task_created', task_id=task_id, payload={'title': args.title})
        for dep in args.depends or []:
            add_dependency(conn, task_id, dep)
        for f in args.link or []:
            add_resource(conn, task_id, 'touch', resource=f"file:{f}")
        for r in args.resource or []:
            kind, resource = parse_resource_arg(r)
            add_resource(conn, task_id, kind, resource)
        print(task_id)


def list_cmd(args):
    ensure_db()
    query = 'SELECT id, title, status, assignee, priority, due_date, updated_at FROM tasks WHERE 1=1'
    params = []
    if args.status:
        query += ' AND status = ?'
        params.append(args.status)
    if args.assignee:
        query += ' AND assignee = ?'
        params.append(args.assignee)
    if args.me:
        me = os.environ.get('TM_ASSIGNEE') or actor_name()
        query += ' AND assignee = ?'
        params.append(me)
    query += ' ORDER BY priority DESC, updated_at DESC'
    with connect(args.db) as conn:
        cur = conn.execute(query, params)
        rows = [dict_row(r) for r in cur.fetchall()]
        print_table(rows, ['id','title','status','assignee','priority','due_date','updated_at'])


def show_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        task = get_task(conn, args.id)
        if not task:
            sys.exit(f"Task {args.id} not found")
        print(f"[{task['id']}] {task['title']}")
        print(f"status: {task['status']}")
        if task['blocked_reason']:
            print(f"blocked_reason: {task['blocked_reason']}")
        if task['assignee']:
            print(f"assignee: {task['assignee']}")
        if task['due_date']:
            print(f"due: {task['due_date']}")
        if task['priority']:
            print(f"priority: {task['priority']}")
        if task['description']:
            print("\n" + textwrap.fill(task['description'], width=100))
        cur = conn.execute('SELECT depends_on_task_id FROM dependencies WHERE task_id = ?', (args.id,))
        deps = [str(r[0]) for r in cur.fetchall()]
        if deps:
            print(f"depends_on: {', '.join(deps)}")
        cur = conn.execute('SELECT kind, resource FROM resources WHERE task_id = ? ORDER BY id', (args.id,))
        res = [f"{r['kind']}:{r['resource']}" for r in cur.fetchall()]
        if res:
            print(f"resources: {', '.join(res)}")
        cur = conn.execute('SELECT id, created_at, file, content FROM notes WHERE task_id = ? ORDER BY id', (args.id,))
        notes = cur.fetchall()
        if notes:
            print("\nnotes:")
            for n in notes:
                prefix = f"- {n['id']} {n['created_at']}"
                if n['file']:
                    prefix += f" file={n['file']}"
                print(prefix)
                print(textwrap.indent(textwrap.fill(n['content'], width=100), '  '))


def update_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        task = get_task(conn, args.id)
        if not task:
            sys.exit(f"Task {args.id} not found")
        fields = []
        params = []
        if args.title:
            fields.append('title = ?')
            params.append(args.title)
        if args.description is not None:
            fields.append('description = ?')
            params.append(args.description)
        if args.assignee is not None:
            fields.append('assignee = ?')
            params.append(args.assignee)
        if args.priority is not None:
            fields.append('priority = ?')
            params.append(args.priority)
        if args.due is not None:
            fields.append('due_date = ?')
            params.append(args.due)
        if not fields:
            return
        fields.append('updated_at = ?')
        params.append(now_iso())
        params.append(args.id)
        conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", params)
        add_event(conn, 'task_updated', task_id=args.id)


def status_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        task = get_task(conn, args.id)
        if not task:
            sys.exit(f"Task {args.id} not found")
        new_status = args.status
        if new_status not in STATUSES:
            sys.exit(f"Invalid status {new_status}")
        conn.execute('UPDATE tasks SET status = ?, updated_at = ?, blocked_reason = CASE WHEN ? != "blocked" THEN NULL ELSE blocked_reason END WHERE id = ?',
                     (new_status, now_iso(), new_status, args.id))
        add_event(conn, 'task_status_changed', task_id=args.id, payload={'status': new_status})
        if new_status == 'completed':
            on_task_completed(conn, args.id)


def start_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        blockers = unmet_dependencies(conn, args.id)
        if blockers:
            reason = f"Blocked by: {', '.join(map(str, blockers))}"
            conn.execute('UPDATE tasks SET status = ?, blocked_reason = ?, updated_at = ? WHERE id = ?',
                         ('blocked', reason, now_iso(), args.id))
            add_event(conn, 'task_blocked', task_id=args.id, payload={'reason': reason, 'blockers': blockers})
            print(reason)
            return
        conn.execute('UPDATE tasks SET status = ?, blocked_reason = NULL, updated_at = ? WHERE id = ?',
                     ('in_progress', now_iso(), args.id))
        add_event(conn, 'task_started', task_id=args.id)


def block_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        conn.execute('UPDATE tasks SET status = ?, blocked_reason = ?, updated_at = ? WHERE id = ?',
                     ('blocked', args.reason or '', now_iso(), args.id))
        add_event(conn, 'task_blocked', task_id=args.id, payload={'reason': args.reason or ''})


def unblock_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        conn.execute('UPDATE tasks SET status = ?, blocked_reason = NULL, updated_at = ? WHERE id = ?',
                     ('pending', now_iso(), args.id))
        add_event(conn, 'task_unblocked', task_id=args.id)


def complete_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        conn.execute('UPDATE tasks SET status = ?, blocked_reason = NULL, updated_at = ? WHERE id = ?',
                     ('completed', now_iso(), args.id))
        add_event(conn, 'task_completed', task_id=args.id, payload={'message': args.message})
        on_task_completed(conn, args.id)


def depend_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        add_dependency(conn, args.id, args.on)


def undepend_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        conn.execute('DELETE FROM dependencies WHERE task_id = ? AND depends_on_task_id = ?', (args.id, args.on))
        add_event(conn, 'dependency_removed', task_id=args.id, payload={'on': args.on})


def assign_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        conn.execute('UPDATE tasks SET assignee = ?, updated_at = ? WHERE id = ?', (args.assignee, now_iso(), args.id))
        add_event(conn, 'task_assigned', task_id=args.id, payload={'assignee': args.assignee})


def note_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        conn.execute('INSERT INTO notes(task_id, content, file, created_at) VALUES (?,?,?,?)',
                     (args.id, args.text, args.file, now_iso()))
        add_event(conn, 'note_added', task_id=args.id, payload={'file': args.file})


def link_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        add_resource(conn, args.id, 'touch', resource=f"file:{args.file}")


def resource_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        for res in args.resource:
            kind, resource = parse_resource_arg(res)
            add_resource(conn, args.id, kind, resource)


def watch_cmd(args):
    ensure_db()
    last_id = args.since or 0
    filt_assignee = args.assignee
    if args.me:
        filt_assignee = os.environ.get('TM_ASSIGNEE') or actor_name()
    with connect(args.db) as conn:
        while True:
            rows = conn.execute('SELECT * FROM events WHERE id > ? ORDER BY id ASC', (last_id,)).fetchall()
            out = []
            for r in rows:
                r = dict_row(r)
                if filt_assignee:
                    # filter events to tasks assigned to assignee
                    task_id = r.get('target_task_id') or r.get('task_id')
                    if task_id:
                        task = get_task(conn, task_id)
                        if not task or task.get('assignee') != filt_assignee:
                            continue
                out.append(r)
            for e in out:
                last_id = e['id']
                line = f"{e['id']} {e['created_at']} {e['type']} task={e['task_id']} target={e['target_task_id']} actor={e['actor']}"
                if e['payload']:
                    try:
                        payload = json.loads(e['payload'])
                        detail = ' '.join(f"{k}={v}" for k, v in payload.items())
                    except Exception:
                        detail = e['payload']
                    line += f" {detail}"
                print(line)
            if not args.follow:
                break
            time.sleep(args.interval)


def doctor_cmd(args):
    ensure_db()
    with connect(args.db) as conn:
        # find cycles
        cycles = find_cycles(conn)
        for cyc in cycles:
            add_event(conn, 'doctor_cycle', payload={'cycle': cyc})
            print(f"cycle detected: {' -> '.join(map(str, cyc))}")
        # auto-unblock tasks with all deps completed
        cur = conn.execute("SELECT id FROM tasks WHERE status = 'blocked'")
        blocked = [r[0] for r in cur.fetchall()]
        for tid in blocked:
            blockers = unmet_dependencies(conn, tid)
            if not blockers:
                conn.execute('UPDATE tasks SET status = ?, blocked_reason = NULL, updated_at = ? WHERE id = ?', ('pending', now_iso(), tid))
                add_event(conn, 'task_unblocked', task_id=tid)
                print(f"unblocked {tid}")


def get_task(conn, task_id: int) -> Optional[Dict]:
    r = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    return dict_row(r) if r else None


def unmet_dependencies(conn, task_id: int) -> List[int]:
    rows = conn.execute(
        """
        SELECT d.depends_on_task_id, t.status FROM dependencies d
        JOIN tasks t ON t.id = d.depends_on_task_id
        WHERE d.task_id = ?
        """,
        (task_id,)
    ).fetchall()
    return [r[0] for r in rows if r[1] != 'completed']


def add_dependency(conn, task_id: int, depends_on: int):
    conn.execute('INSERT OR IGNORE INTO dependencies(task_id, depends_on_task_id) VALUES (?,?)', (task_id, depends_on))
    add_event(conn, 'dependency_added', task_id=task_id, payload={'on': depends_on})
    blockers = unmet_dependencies(conn, task_id)
    if blockers:
        reason = f"Blocked by: {', '.join(map(str, blockers))}"
        conn.execute('UPDATE tasks SET status = ?, blocked_reason = ?, updated_at = ? WHERE id = ?',
                     ('blocked', reason, now_iso(), task_id))
        add_event(conn, 'task_blocked', task_id=task_id, payload={'reason': reason, 'blockers': blockers})


from typing import Tuple

def parse_resource_arg(text: str) -> Tuple[str, str]:
    if ':' not in text:
        raise SystemExit("Resource must be in KIND:VALUE form, e.g., modifies:endpoint:GET /api/foo")
    kind, resource = text.split(':', 1)
    if kind not in RESOURCE_KINDS:
        raise SystemExit(f"Invalid resource kind {kind}")
    return kind, resource


def add_resource(conn, task_id: int, kind: str, resource: str):
    conn.execute('INSERT INTO resources(task_id, kind, resource, created_at) VALUES (?,?,?,?)', (task_id, kind, resource, now_iso()))
    add_event(conn, 'resource_added', task_id=task_id, payload={'kind': kind, 'resource': resource})


def on_task_completed(conn, task_id: int):
    # notify dependents
    rows = conn.execute('SELECT task_id FROM dependencies WHERE depends_on_task_id = ?', (task_id,)).fetchall()
    dependents = [r[0] for r in rows]
    for dep in dependents:
        blockers = unmet_dependencies(conn, dep)
        if not blockers:
            # auto-unblock if previously blocked by deps
            t = get_task(conn, dep)
            if t and t['status'] == 'blocked':
                conn.execute('UPDATE tasks SET status = ?, blocked_reason = NULL, updated_at = ? WHERE id = ?', ('pending', now_iso(), dep))
                add_event(conn, 'task_unblocked', task_id=dep)
        add_event(conn, 'dependency_satisfied', task_id=task_id, target_task_id=dep)

    # impact analysis via resources
    my_res = conn.execute('SELECT kind, resource FROM resources WHERE task_id = ?', (task_id,)).fetchall()
    for r in my_res:
        kind = r['kind']; res = r['resource']
        if kind == 'removes':
            impacted = conn.execute(
                """
                SELECT DISTINCT task_id FROM resources WHERE resource = ? AND kind IN ('touch','adds','modifies','depends') AND task_id != ?
                """, (res, task_id)
            ).fetchall()
            for t in impacted:
                add_event(conn, 'impact_conflict', task_id=task_id, target_task_id=t[0], payload={'resource': res, 'action': 'removed'})
        elif kind == 'modifies':
            impacted = conn.execute(
                """
                SELECT DISTINCT task_id FROM resources WHERE resource = ? AND kind IN ('depends','touch','modifies') AND task_id != ?
                """, (res, task_id)
            ).fetchall()
            for t in impacted:
                add_event(conn, 'impact_notice', task_id=task_id, target_task_id=t[0], payload={'resource': res, 'action': 'modified'})
        elif kind == 'adds':
            impacted = conn.execute(
                """
                SELECT DISTINCT task_id FROM resources WHERE resource = ? AND kind IN ('depends') AND task_id != ?
                """, (res, task_id)
            ).fetchall()
            for t in impacted:
                add_event(conn, 'impact_notice', task_id=task_id, target_task_id=t[0], payload={'resource': res, 'action': 'added'})


def find_cycles(conn) -> list[list[int]]:
    # simple DFS over tasks/dependencies
    graph = {}
    rows = conn.execute('SELECT task_id, depends_on_task_id FROM dependencies').fetchall()
    for r in rows:
        graph.setdefault(r[0], []).append(r[1])
    cycles = []
    visited = set()

    def dfs(node, stack):
        visited.add(node)
        stack.append(node)
        for neigh in graph.get(node, []):
            if neigh in stack:
                i = stack.index(neigh)
                cycles.append(stack[i:] + [neigh])
            elif neigh not in visited:
                dfs(neigh, stack)
        stack.pop()

    for node in list(graph.keys()):
        if node not in visited:
            dfs(node, [])
    return cycles


def build_parser():
    p = argparse.ArgumentParser(prog='tm', description='Local task manager for parallel AI agents')
    p.add_argument('--db', help='Path to sqlite database (default: TM_DB or ~/.gpt5/tasks.db)')

    sub = p.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('init', help='Initialize database')
    s.set_defaults(func=init_cmd)

    s = sub.add_parser('add', help='Add a new task')
    s.add_argument('title')
    s.add_argument('-d','--description')
    s.add_argument('-a','--assignee')
    s.add_argument('-p','--priority', type=int, default=0)
    s.add_argument('--due')
    s.add_argument('--depends', type=int, nargs='*')
    s.add_argument('--link', nargs='*', help='File paths to link (stored as file:PATH resources)')
    s.add_argument('--resource', nargs='*', help='KIND:VALUE, e.g., removes:endpoint:DELETE /api/foo')
    s.set_defaults(func=add_cmd)

    s = sub.add_parser('list', help='List tasks')
    s.add_argument('--status', choices=STATUSES)
    s.add_argument('--assignee')
    s.add_argument('--me', action='store_true')
    s.set_defaults(func=list_cmd)

    s = sub.add_parser('show', help='Show task details')
    s.add_argument('id', type=int)
    s.set_defaults(func=show_cmd)

    s = sub.add_parser('update', help='Update task fields')
    s.add_argument('id', type=int)
    s.add_argument('--title')
    s.add_argument('--description')
    s.add_argument('--assignee')
    s.add_argument('--priority', type=int)
    s.add_argument('--due')
    s.set_defaults(func=update_cmd)

    s = sub.add_parser('status', help='Set task status')
    s.add_argument('id', type=int)
    s.add_argument('status', choices=STATUSES)
    s.set_defaults(func=status_cmd)

    s = sub.add_parser('start', help='Start a task if dependencies are satisfied; otherwise mark blocked')
    s.add_argument('id', type=int)
    s.set_defaults(func=start_cmd)

    s = sub.add_parser('block', help='Explicitly mark a task blocked')
    s.add_argument('id', type=int)
    s.add_argument('-r','--reason')
    s.set_defaults(func=block_cmd)

    s = sub.add_parser('unblock', help='Mark a blocked task as pending')
    s.add_argument('id', type=int)
    s.set_defaults(func=unblock_cmd)

    s = sub.add_parser('complete', help='Mark task completed and run impact checks')
    s.add_argument('id', type=int)
    s.add_argument('-m','--message')
    s.set_defaults(func=complete_cmd)

    s = sub.add_parser('depend', help='Add dependency to a task')
    s.add_argument('id', type=int)
    s.add_argument('--on', type=int, required=True)
    s.set_defaults(func=depend_cmd)

    s = sub.add_parser('undepend', help='Remove a dependency')
    s.add_argument('id', type=int)
    s.add_argument('--on', type=int, required=True)
    s.set_defaults(func=undepend_cmd)

    s = sub.add_parser('assign', help='Assign a task to a person/agent')
    s.add_argument('id', type=int)
    s.add_argument('-a','--assignee', required=True)
    s.set_defaults(func=assign_cmd)

    s = sub.add_parser('note', help='Add a note to a task')
    s.add_argument('id', type=int)
    s.add_argument('text')
    s.add_argument('--file', help='Reference a file path this note pertains to')
    s.set_defaults(func=note_cmd)

    s = sub.add_parser('link', help='Link a file path to task (shorthand for resource touch:file:PATH)')
    s.add_argument('id', type=int)
    s.add_argument('file')
    s.set_defaults(func=link_cmd)

    s = sub.add_parser('resource', help='Attach resource annotation(s) to task')
    s.add_argument('id', type=int)
    s.add_argument('resource', nargs='+')
    s.set_defaults(func=resource_cmd)

    s = sub.add_parser('watch', help='Stream events to the console')
    s.add_argument('--since', type=int)
    s.add_argument('--follow', action='store_true')
    s.add_argument('--interval', type=float, default=1.0)
    s.add_argument('--assignee')
    s.add_argument('--me', action='store_true', help='Filter to events for TM_ASSIGNEE or current actor')
    s.set_defaults(func=watch_cmd)

    s = sub.add_parser('doctor', help='Integrity checks and auto-fixes')
    s.set_defaults(func=doctor_cmd)

    return p


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
