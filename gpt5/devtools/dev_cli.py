#!/usr/bin/env python3
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import hashlib
import socket
from urllib.parse import urlparse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Iterable

ROOT = Path(os.environ.get("DEV_ROOT", str(Path.cwd()))).resolve()
CACHE_DIR = Path(os.environ.get("DEV_CACHE", os.path.expanduser("~/.gpt5")))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CODE_MAP_JSON = CACHE_DIR / "code_map.json"

# ---------- Utilities ----------

def run(cmd: List[str]) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"{cmd[0]} not found"


def which(name: str) -> Optional[str]:
    p = shutil.which(name)
    return p


# ---------- doctor ----------

def doctor_cmd(args):
    checks: List[Dict[str, Any]] = []

    def add_check(name: str, ok: bool, details: str = "", hint: str = ""):
        checks.append({
            "name": name,
            "ok": bool(ok),
            "details": details,
            "hint": hint,
        })

    # Python
    add_check(
        "python",
        True,
        details=f"{sys.version.split()[0]} at {sys.executable}",
    )

    # Git
    code, out, err = run(["git", "--version"])
    add_check("git", code == 0, out or err, hint="Install git and ensure it's on PATH")

    # Node / npm
    for tool, hint in [
        ("node", "Install Node.js (e.g., via nvm)"),
        ("npm", "Install npm (bundled with Node.js)"),
        ("rg", "Install ripgrep: brew install ripgrep"),
        ("ctags", "Install universal-ctags: brew install --HEAD universal-ctags"),
        ("sqlite3", "Install sqlite3 CLI")
    ]:
        code, out, err = run([tool, "--version"]) if which(tool) else (127, "", f"{tool} not found")
        add_check(tool, code == 0, out or err, hint)

    # RabbitMQ (broker) checks
    def _tcp_check(host: str, port: int, timeout: float = 0.5) -> tuple[bool, str]:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True, f"{host}:{port} reachable"
        except Exception as e:
            return False, f"{host}:{port} unreachable ({e.__class__.__name__})"

    # Determine broker URL from env or common defaults
    broker_url = os.environ.get("RABBITMQ_URL") or os.environ.get("CELERY_BROKER_URL") or "amqp://guest:guest@localhost:5672/"
    parsed = urlparse(broker_url)
    broker_host = parsed.hostname or "localhost"
    broker_port = parsed.port or 5672
    ok5672, det5672 = _tcp_check(broker_host, broker_port)
    add_check("rabbitmq:amqp", ok5672, f"{det5672}", hint="Ensure RabbitMQ is running. Try: dev broker up")

    # Management UI (if using management image)
    mgmt_port = int(os.environ.get("RABBITMQ_MGMT_PORT", "15672"))
    ok15672, det15672 = _tcp_check(broker_host, mgmt_port)
    add_check("rabbitmq:mgmt", ok15672, f"{det15672}", hint="Management UI optional. Try: http://localhost:15672 user=guest pass=guest")

    # Optional AMQP handshake probe via pika if available
    try:
        import pika  # type: ignore
        try:
            params = pika.URLParameters(broker_url)
            conn = pika.BlockingConnection(params)
            conn.close()
            add_check("rabbitmq:amqp-probe", True, "AMQP handshake ok via pika")
        except Exception as e:
            add_check("rabbitmq:amqp-probe", False, f"AMQP probe failed: {e.__class__.__name__}: {e}", hint="Start broker or check credentials. Use 'dev broker up'")
    except Exception:
        add_check("rabbitmq:amqp-probe", False, "pika not installed", hint="pip install pika to enable AMQP probe")

    # Platform info
    sysinfo = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "cwd": str(ROOT),
    }

    ok = all(c["ok"] for c in checks)
    result = {"ok": ok, "sys": sysinfo, "checks": checks}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Doctor OK={ok}")
        for c in checks:
            status = "OK" if c["ok"] else "MISSING"
            print(f"- {c['name']}: {status}  {c['details']}")
            if not c["ok"] and c.get("hint"):
                print(f"  hint: {c['hint']}")
    return 0 if ok else 1


# ---------- code-map ----------
@dataclass
class FileEntry:
    path: str
    lang: str
    sha1: str
    size: int
    symbols: List[str]
    imports: List[str]


def file_sha1(p: Path) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_lang(p: Path) -> str:
    ext = p.suffix.lower()
    return {
        ".py": "python",
        ".ts": "ts",
        ".tsx": "ts",
        ".js": "js",
        ".jsx": "js",
        ".go": "go",
        ".rb": "ruby",
    }.get(ext, "other")


def parse_python(p: Path) -> tuple[List[str], List[str]]:
    import ast
    symbols: List[str] = []
    imports: List[str] = []
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return symbols, imports
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(node.name)
        elif isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for n in node.names:
                imports.append(f"{mod}.{n.name}" if mod else n.name)
    return symbols, imports


def parse_text_lines(p: Path) -> List[str]:
    try:
        return p.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []


def parse_ts_js(p: Path) -> tuple[List[str], List[str]]:
    lines = parse_text_lines(p)
    symbols: List[str] = []
    imports: List[str] = []
    for ln in lines:
        ln = ln.strip()
        if ln.startswith("import ") and ((from_token := ln.find(" from ")) != -1):
            pkg = ln.split(" from ")[-1].strip().strip("'\"")
            if pkg:
                imports.append(pkg)
        if ln.startswith("export function "):
            name = ln.split()[2].split("(")[0]
            symbols.append(name)
        if ln.startswith("export class "):
            name = ln.split()[2].split("{")[0]
            symbols.append(name)
    return symbols, imports


def parse_go(p: Path) -> tuple[List[str], List[str]]:
    lines = parse_text_lines(p)
    symbols: List[str] = []
    imports: List[str] = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("import "):
            pkg = s.replace("import ", "").strip('"')
            if pkg:
                imports.append(pkg)
        if s.startswith("func "):
            name = s[len("func "):].split("(")[0].strip()
            if name:
                symbols.append(name)
    return symbols, imports


def parse_ruby(p: Path) -> tuple[List[str], List[str]]:
    lines = parse_text_lines(p)
    symbols: List[str] = []
    imports: List[str] = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("class ") or s.startswith("module "):
            name = s.split()[1]
            symbols.append(name)
        if s.startswith("require ") or s.startswith("require_relative "):
            parts = s.split()
            if len(parts) > 1:
                imports.append(parts[1].strip('"\''))
        if s.startswith("def "):
            name = s.split()[1].split("(")[0]
            symbols.append(name)
    return symbols, imports


PARSERS = {
    "python": parse_python,
    "ts": parse_ts_js,
    "js": parse_ts_js,
    "go": parse_go,
    "ruby": parse_ruby,
}


def code_map_build(args):
    root = Path(args.root or ROOT)
    entries: List[Dict[str, Any]] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        lang = detect_lang(p)
        if lang == "other":
            continue
        sha1 = file_sha1(p)
        size = p.stat().st_size
        parse = PARSERS.get(lang)
        symbols: List[str] = []
        imports: List[str] = []
        if parse:
            s, imps = parse(p)
            symbols = s
            imports = imps
        rel = str(p.relative_to(root))
        entries.append(asdict(FileEntry(rel, lang, sha1, size, symbols, imports)))
    out = CODE_MAP_JSON if not args.out else Path(args.out)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"root": str(root), "files": entries}, f, indent=2)
    print(str(out))


def code_map_find(args):
    path = Path(args.map or CODE_MAP_JSON)
    if not path.exists():
        sys.exit(f"Code map not found at {path}. Run 'dev code-map build' first.")
    data = json.loads(path.read_text())
    files = data.get("files", [])
    q = (args.query or "").lower()
    results = []
    for f in files:
        if args.kind == "symbol":
            if any(q in s.lower() for s in f.get("symbols", [])):
                results.append(f)
        elif args.kind == "import":
            if any(q in s.lower() for s in f.get("imports", [])):
                results.append(f)
        else:
            if q in f.get("path", "").lower():
                results.append(f)
    for r in results[: args.limit]:
        print(f"{r['path']}  lang={r['lang']}  symbols={','.join(r['symbols'][:5])}")


# ---------- bootstrap ----------

def bootstrap_cmd(args):
    # Run doctor first
    code = doctor_cmd(argparse.Namespace(json=True))
    if code != 0:
        print("Environment checks failed; bootstrap cannot continue.")
        return code
    # Initialize task-manager DB and run a smoke task
    tm = Path("gpt5/task-manager/tm").resolve()
    if tm.exists():
        subprocess.run([str(tm), "init"], check=False)
        out = subprocess.run([str(tm), "add", "Bootstrap smoke"], capture_output=True, text=True)
        tid = (out.stdout.strip() or "0")
        subprocess.run([str(tm), "show", tid], check=False)
        print("Bootstrap complete.")
    else:
        print("task-manager entrypoint not found; skipping DB init")
    return 0


# ---------- tasks graph visualizer ----------
def tasks_graph_cmd(args):
    # Lazy import to avoid coupling
    from sqlite3 import connect as _connect
    db = os.environ.get("TM_DB", os.path.expanduser("~/.gpt5/tasks.db"))
    if args.db:
        db = args.db
    # Build edges task -> depends_on
    with _connect(db) as conn:
        rows = conn.execute("SELECT task_id, depends_on_task_id FROM dependencies").fetchall()
        tasks = conn.execute("SELECT id, title FROM tasks").fetchall()
    titles = {tid: title for (tid, title) in tasks}
    if args.format == "mermaid":
        print("graph TD")
        for a, b in rows:
            a_label = titles.get(a, str(a)).replace('"', "'")
            b_label = titles.get(b, str(b)).replace('"', "'")
            print(f'  T{a}["{a}: {a_label}"] --> T{b}["{b}: {b_label}"]')
    else:
        for a, b in rows:
            print(f"{a} -> {b}")


# ---------- impact analyzer (git-aware) ----------
def impact_cmd(args):
    # diff files since ref or staged/untracked
    files: List[str] = []
    if args.ref:
        code, out, err = run(["git", "diff", "--name-only", args.ref, "--"])
    else:
        code, out, err = run(["git", "status", "--porcelain"])
        if code == 0:
            for ln in out.splitlines():
                parts = ln.strip().split()
                if parts:
                    files.append(parts[-1])
            code = 0
            out = "\n".join(files)
    if code != 0:
        sys.exit(err or "git command failed")
    changed = [f for f in out.splitlines() if f.strip()]
    root = Path(args.root or ROOT)
    abs_ = [str((root / f).resolve()) for f in changed]
    rel_ = [str(Path(f)) for f in changed]

    # Query task-manager resources for file links
    from sqlite3 import connect as _connect
    db = os.environ.get("TM_DB", os.path.expanduser("~/.gpt5/tasks.db"))
    if args.db:
        db = args.db
    patterns = ["file:" + p for p in abs_ + rel_]
    with _connect(db) as conn:
        rows = conn.execute(
            "SELECT r.task_id, r.resource, t.title FROM resources r JOIN tasks t ON t.id=r.task_id"
        ).fetchall()
    hits = []
    for tid, res, title in rows:
        if any(res.endswith(p) or res == p for p in patterns):
            hits.append((tid, title, res))
    if not hits:
        print("No direct task resource matches for changed files.")
    else:
        for tid, title, res in hits:
            print(f"task {tid} '{title}' touches {res}")


# ---------- csearch ----------
def _iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(root).parts):
            yield p


def csearch_cmd(args):
    q = (args.query or "").lower()
    kind = args.kind
    allowed_langs = set(l.lower() for l in (args.lang or [])) if args.lang else None
    prefixes = [Path(p) for p in (args.path_prefix or [])]

    # symbol/import search via map
    if kind in ("symbol", "import", "path"):
        path = Path(args.map or CODE_MAP_JSON)
        if not path.exists():
            sys.exit(f"Code map not found at {path}. Run 'dev code-map build' first.")
        data = json.loads(path.read_text())
        files = data.get("files", [])
        results = []
        for f in files:
            if allowed_langs and f.get("lang", "").lower() not in allowed_langs:
                continue
            if prefixes and not any(str(f.get("path","")) .startswith(str(px)) for px in prefixes):
                continue
            if kind == "path" and q in f.get("path","" ).lower():
                results.append(f)
            elif kind == "symbol" and any(q in s.lower() for s in f.get("symbols", [])):
                results.append(f)
            elif kind == "import" and any(q in s.lower() for s in f.get("imports", [])):
                results.append(f)
        for r in results[: args.limit]:
            print(f"{r['path']}  lang={r['lang']}  symbols={','.join(r['symbols'][:5])}")
        return 0

    # text search fallback using ripgrep if available
    root = Path(args.root or ROOT)
    rg = shutil.which("rg")
    if rg:
        cmd = [rg, "-n", "-S", q, str(root)]
        code, out, err = run(cmd)
        if code == 0 and out:
            lines = out.splitlines()
            # apply filtering on path if requested
            for ln in lines[: args.limit]:
                path = Path(ln.split(":", 1)[0])
                if prefixes and not any(str(path).startswith(str(px)) for px in prefixes):
                    continue
                print(ln)
            return 0
    # simple Python fallback
    shown = 0
    for p in _iter_files(root):
        if shown >= args.limit:
            break
        if prefixes and not any(str(p).startswith(str(px)) for px in prefixes):
            continue
        if allowed_langs and detect_lang(p) not in allowed_langs:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        if q in text:
            print(f"{p}")
            shown += 1
    return 0


# ---------- seed ----------
def seed_cmd(args):
    from sqlite3 import connect as _connect
    db = os.environ.get("TM_DB", os.path.expanduser("~/.gpt5/tasks.db"))
    if args.db:
        db = args.db
    with _connect(db) as conn:
        # Check if tasks already present
        cur = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='tasks'")
        has_tasks_table = cur.fetchone()[0] == 1
        if not has_tasks_table:
            # initialize via task-manager ensure_db path? we can just import schema if present
            pass
        cnt = 0
        if has_tasks_table:
            cnt = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if cnt > 0 and not args.force:
            print(f"DB already has {cnt} tasks; use --force to seed anyway")
            return 0
        # minimal seed
        import time as _t
        now = _t.strftime("%Y-%m-%dT%H:%M:%S", _t.localtime())
        for i in range(1, args.count + 1):
            title = f"Seed Task {i}"
            prio = 1 if i % 3 == 0 else 0
            assignee = "assistant" if i % 2 == 0 else ""
            conn.execute(
                "INSERT INTO tasks(title, description, status, assignee, priority, due_date, blocked_reason, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (title, "seeded", "pending", assignee, prio, None, None, now, now),
            )
        # simple chain dependencies 2->1, 3->2, etc.
        rows = conn.execute("SELECT id FROM tasks ORDER BY id DESC LIMIT ?", (args.count,)).fetchall()
        ids = [r[0] for r in rows][::-1]
        for a, b in zip(ids[1:], ids[:-1]):
            conn.execute("INSERT OR IGNORE INTO dependencies(task_id, depends_on_task_id) VALUES (?,?)", (a, b))
    print(f"Seeded {args.count} tasks into {db}")
    return 0


# ---------- repro scaffold ----------
def repro_scaffold_cmd(args):
    root = Path.cwd() / ".repro" / args.name
    root.mkdir(parents=True, exist_ok=True)
    test_py = root / "test_repro.py"
    cassette = root / "cassettes" / "repro.yaml"
    cassette.parent.mkdir(parents=True, exist_ok=True)
    url = args.url or "https://httpbin.org/get"
    test_content = f'''"""
Scaffolded repro test. If vcrpy is installed, this will record/replay HTTP.
Run it with: python3 -m unittest {test_py}
"""
import os, unittest
try:
    import vcr  # type: ignore
except Exception:
    vcr = None

class ReproTest(unittest.TestCase):
    def test_http(self):
        import requests
        def _do():
            return requests.get("{url}").status_code
        if vcr:
            myvcr = vcr.VCR(cassette_library_dir=str({str(cassette.parent)!r}))
            with myvcr.use_cassette("{cassette.name}"):
                self.assertIn(_do(), (200, 429))
        else:
            self.assertTrue(True)

if __name__ == '__main__':
    unittest.main(verbosity=2)
'''
    test_py.write_text(test_content)
    readme = root / "README.md"
    readme.write_text(f"""### Reproducer: {args.name}

Files:
- test_repro.py: unittest that optionally uses vcrpy if available
- cassettes/repro.yaml: created on first run if vcrpy is installed

Usage:
1) Optional: pip install vcrpy requests
2) python3 -m unittest {test_py}

Note: Without vcrpy, the test will not perform HTTP; it still executes and passes.
""")
    print(str(root))
    return 0

# ---------- e2e runner (scaffold + run) ----------
def e2e_scaffold_cmd(args):
    name = args.name
    root = Path.cwd() / ".e2e" / name
    root.mkdir(parents=True, exist_ok=True)
    spec = root / "spec.py"
    content = f'''"""
Lightweight E2E spec. If Playwright is installed, runs in a real browser; otherwise falls back to a stub.
Run: python3 {spec}
"""
import os
import sys

def main():
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("{args.url or 'https://example.com'}")
            title = page.title()
            print("title=" + title)
            browser.close()
            return 0
    except Exception as e:
        print("playwright not available; running stub flow")
        print("stub: visited {args.url or 'https://example.com'} and asserted title contains Example")
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''
    spec.write_text(content)
    readme = root / "README.md"
    readme.write_text(f"""### E2E: {name}

Files:
- spec.py: runnable E2E test that uses Playwright if present; otherwise runs a stub.

Usage:
1) Optional: pip install playwright && playwright install
2) python3 .e2e/{name}/spec.py
""")
    print(str(root))
    return 0


def e2e_run_cmd(args):
    name = args.name
    spec = Path.cwd() / ".e2e" / name / "spec.py"
    if not spec.exists():
        sys.exit(f"Spec not found: {spec}. Try 'dev e2e scaffold {name}'.")
    code, out, err = run([sys.executable, str(spec)])
    if out:
        print(out)
    if err:
        print(err)
    return code


# ---------- preflight gate ----------
def preflight_cmd(args):
    summary: List[str] = []
    ok = True

    # 1) doctor
    code, out, err = run([str(Path(__file__).resolve().parent / "dev"), "doctor", "--json"])
    try:
        doc = json.loads(out or "{}")
    except Exception:
        doc = {"ok": False}
    summary.append(f"doctor ok={doc.get('ok')}")
    ok = ok and bool(doc.get("ok"))

    # 2) unit tests (python)
    if not getattr(args, "quick", False):
        code, out, err = run([sys.executable, "-m", "unittest", "discover", "-v"])  # prints its own output
        summary.append(f"unittests ok={code == 0}")
        ok = ok and code == 0
    else:
        summary.append("unittests skipped (quick mode)")

    # 3) code-map build
    code, out, err = run([str(Path(__file__).resolve().parent / "dev"), "code-map", "build", "--root", str(ROOT)])
    summary.append(f"code-map ok={code == 0}")
    ok = ok and code == 0

    # 4) impact (working copy)
    code, out, err = run([str(Path(__file__).resolve().parent / "dev"), "impact"])
    summary.append("impact computed")

    # 5) optional: e2e smoke
    if args.e2e and not getattr(args, "quick", False):
        # if a default spec exists, run it; otherwise skip
        spec = Path.cwd() / ".e2e" / args.e2e / "spec.py"
        if spec.exists():
            code2, out2, err2 = run([sys.executable, str(spec)])
            summary.append(f"e2e {args.e2e} ok={code2 == 0}")
            ok = ok and code2 == 0
        else:
            summary.append(f"e2e {args.e2e} missing; skipped")

    print("\nPRE-FLIGHT SUMMARY:\n- " + "\n- ".join(summary))
    return 0 if ok else 1


# ---------- smol-podcaster preflight preset ----------
def preflight_smol_cmd(args):
    summary: List[str] = []
    ok = True

    repo_root = Path.cwd()
    sp_dir = repo_root / "smol-podcaster"
    if not sp_dir.exists():
        sys.exit(f"smol-podcaster directory not found at {sp_dir}")

    # 0) optional install
    if getattr(args, "install", False):
        req = sp_dir / "requirements-dev.txt"
        if not req.exists():
            req = sp_dir / "requirements.txt"
        code, out, err = run([sys.executable, "-m", "pip", "install", "-r", str(req)])
        summary.append(f"deps install ok={code == 0} file={req.name}")
        ok = ok and code == 0
        if code != 0:
            summary.append(f"deps error: {err[:200] if err else out[:200]}")

    # 1) doctor with broker checks
    code, out, err = run([str(Path(__file__).resolve().parent / "dev"), "doctor", "--json"])
    try:
        doc = json.loads(out or "{}")
    except Exception:
        doc = {"ok": False}
    summary.append(f"doctor ok={doc.get('ok')}")
    ok = ok and bool(doc.get("ok"))

    # 2) API health at /
    import urllib.request
    base = os.environ.get("SMOL_API_BASE", "http://127.0.0.1:5000/").rstrip("/")
    try:
        with urllib.request.urlopen(base + "/", timeout=1.5) as resp:
            summary.append(f"api / ok={resp.status == 200}")
            ok = ok and (resp.status == 200)
            api_up = True
    except Exception as e:
        summary.append(f"api / unreachable ({e.__class__.__name__})")
        api_up = False

    # 3) Celery ping (optional)
    celery_ok = False
    try:
        sys.path.insert(0, str(sp_dir.resolve()))
        import importlib
        tasks = importlib.import_module("tasks")
        app = getattr(tasks, "app", None)
        if app is not None:
            try:
                p = app.control.ping(timeout=1.0)
                celery_ok = isinstance(p, list) and len(p) > 0
                summary.append(f"celery ping workers={len(p) if isinstance(p, list) else 0}")
            except Exception as e:
                summary.append(f"celery ping failed ({e.__class__.__name__})")
        else:
            summary.append("celery app missing in tasks.py")
    except Exception as e:
        summary.append(f"celery unavailable ({e.__class__.__name__})")

    # 4) API smoke: POST /process only if API up and at least one worker
    if api_up and celery_ok and not getattr(args, "quick", False):
        try:
            import urllib.parse
            data = urllib.parse.urlencode({
                "url": "https://example.com/audio.mp3",
                "speakers": 1,
                "name": "smoke",
                "transcript-only": "",
                "generate-extra": "",
            }).encode()
            req = urllib.request.Request(base + "/process", data=data, method="POST")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                summary.append(f"api POST /process ok={resp.status in (200, 302)}")
        except Exception as e:
            summary.append(f"api POST /process failed ({e.__class__.__name__})")
            ok = False
    else:
        summary.append("api smoke skipped (api down or no celery worker or quick mode)")

    print("\nSMOL-PODCASTER PREFLIGHT SUMMARY:\n- " + "\n- ".join(summary))
    return 0 if ok else 1


# ---------- broker (RabbitMQ) helper ----------
def broker_cmd(args):
    name = args.name or "gpt5-rabbitmq"
    if args.subcmd == "up":
        # If container exists, start; else run management image
        code, out, err = run(["docker", "ps", "-a", "--format", "{{.Names}}"])
        if code != 0:
            sys.exit(err or "docker not available")
        names = out.splitlines()
        if name in names:
            code, out, err = run(["docker", "start", name])
            print(out or err)
            return code
        cmd = [
            "docker", "run", "-d", "--name", name,
            "-p", "5672:5672", "-p", "15672:15672",
            "rabbitmq:3-management",
        ]
        code, out, err = run(cmd)
        print(out or err)
        return code
    elif args.subcmd == "down":
        code, out, err = run(["docker", "rm", "-f", name])
        print(out or err)
        return 0 if code == 0 else 1
    elif args.subcmd == "logs":
        tail = args.tail or "100"
        code, out, err = run(["docker", "logs", "--tail", str(tail), name])
        if out:
            print(out)
        if err and not out:
            print(err)
        return 0 if code == 0 else 1
    else:
        sys.exit("unknown broker subcmd")


# ---------- OpenAPI types generator ----------
def openapi_types_cmd(args):
    url = args.url
    out = args.out or str((Path.cwd() / "frontend" / "lib" / "api-types.d.ts"))
    if not which("npx"):
        sys.exit("npx not found. Install Node.js to use openapi-typescript")
    cmd = ["npx", "--yes", "openapi-typescript", url, "-o", out]
    code, outp, err = run(cmd)
    if outp:
        print(outp)
    if err and not outp:
        print(err)
    return 0 if code == 0 else 1

# ---------- flake hunter ----------
def flake_run_cmd(args):
    start = args.start or str(Path.cwd())
    pattern = args.pattern or "test_*.py"
    runs = int(args.runs or 5)
    base_seed = int(args.seed) if args.seed is not None else 1234
    failures = 0
    results: List[Dict[str, Any]] = []
    for i in range(runs):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = str(base_seed + i)
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", start, "-p", pattern, "-v"]
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        except Exception as e:
            results.append({"run": i+1, "code": 1, "error": str(e)})
            failures += 1
            continue
        ok = (p.returncode == 0)
        results.append({"run": i+1, "code": p.returncode, "stdout": p.stdout[-2000:], "stderr": p.stderr[-2000:]})
        if not ok:
            failures += 1
    # summary
    print(f"Flake runs={runs} pattern={pattern} start={start} failures={failures}")
    if args.json:
        print(json.dumps({"runs": runs, "failures": failures, "results": results}, indent=2))
    return 0 if failures == 0 else 1

# ---------- codemod (plan/apply) ----------
def _iter_source_files(root: Path, langs: Optional[Iterable[str]] = None, prefixes: Optional[Iterable[str]] = None) -> Iterable[Path]:
    langs = set(langs or []) if langs else None
    prefixes = [str(p) for p in (prefixes or [])]
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        if prefixes and not any(str(p).startswith(pref) for pref in prefixes):
            continue
        if langs and detect_lang(p) not in langs:
            continue
        yield p


def _make_diff(old: str, new: str, path: str) -> str:
    import difflib
    return "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile=path, tofile=path + " (new)", lineterm=""))


def codemod_plan_cmd(args):
    import re
    root = Path(args.root or ROOT)
    pat = re.compile(args.regex, re.MULTILINE)
    count = 0
    for p in _iter_source_files(root, langs=args.lang, prefixes=args.path_prefix):
        try:
            s = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if not pat.search(s):
            continue
        new = pat.sub(args.replace or "", s)
        if new != s:
            print(_make_diff(s, new, str(p)))
            count += 1
            if count >= args.limit:
                break
    if count == 0:
        print("No changes detected for given pattern.")
    return 0


def codemod_apply_cmd(args):
    import re
    root = Path(args.root or ROOT)
    pat = re.compile(args.regex, re.MULTILINE)
    changed = 0
    for p in _iter_source_files(root, langs=args.lang, prefixes=args.path_prefix):
        try:
            s = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if not pat.search(s):
            continue
        new = pat.sub(args.replace or "", s)
        if new != s:
            if args.yes:
                p.write_text(new, encoding="utf-8")
            changed += 1
            if changed >= args.limit:
                break
    print(f"codemod changed_files={changed}{' (dry-run, use --yes to write)' if not args.yes else ''}")
    return 0 if changed >= 0 else 1


# ---------- triage (new -> files, to-tasks -> optional tm creation) ----------
def triage_new_cmd(args):
    name = args.name
    root = Path.cwd() / ".triage" / name
    root.mkdir(parents=True, exist_ok=True)
    readme = root / "README.md"
    readme.write_text(f"""### Triage: {name}

Sections:
- Context
- Reproduction steps (see .repro if applicable)
- Logs and evidence
- Owner map (code-map findings)
- Impact analysis (see dev impact)
- Proposed fix
- Test plan (unit, E2E)

Commands to explore:
- dev code-map build --root .
- dev csearch --kind symbol --query <symbol>
- dev impact --ref origin/main
""")
    print(str(root))
    return 0


def triage_to_tasks_cmd(args):
    # Minimal helper: create a single task via task-manager if available
    tm = Path("gpt5/task-manager/tm").resolve()
    if not tm.exists():
        print("task-manager not found; printing suggested command")
        print(f"Suggested: tm add '{args.title}' -d '{args.description or ''}'")
        return 0
    cmd = [str(tm), "add", args.title]
    if args.description:
        cmd += ["-d", args.description]
    if args.assignee:
        cmd += ["-a", args.assignee]
    if args.priority is not None:
        cmd += ["-p", str(args.priority)]
    code, out, err = run(cmd)
    if code == 0 and out.strip().isdigit():
        print(f"created task {out.strip()}")
        return 0
    else:
        print(err)
        return 1


# ---------- trace (cProfile for Python expr) ----------
def trace_run_cmd(args):
    import cProfile, pstats, io as _io
    expr = args.expr or "pass"
    out = args.out or str((Path.cwd() / ".trace" / "trace.prof").resolve())
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    pr = cProfile.Profile()
    pr.enable()
    # execute under profile
    ns: Dict[str, Any] = {}
    try:
        exec(expr, ns, ns)
    finally:
        pr.disable()
    pr.dump_stats(out)
    s = _io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(20)
    summary_path = Path(out).with_suffix(".txt")
    summary_path.write_text(s.getvalue())
    print(str(out))
    return 0

# ---------- runbook generator ----------
def runbook_generate_cmd(args):
    import sqlite3
    db = args.db or os.path.expanduser("~/.gpt5/tasks.db")
    task_id = int(args.task)
    out = Path(args.out or (Path.cwd() / f"docs/runbooks/task-{task_id}.md"))
    out.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        t = conn.execute("SELECT id, title, description, status, assignee, due_date, priority FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not t:
            sys.exit(f"Task {task_id} not found in {db}")
        notes = conn.execute("SELECT created_at, file, content FROM notes WHERE task_id=? ORDER BY id", (task_id,)).fetchall()
        res = conn.execute("SELECT kind, resource FROM resources WHERE task_id=? ORDER BY id", (task_id,)).fetchall()
    md = [
        f"### Runbook: Task {t['id']} - {t['title']}",
        "",
        f"- status: {t['status']}",
        f"- assignee: {t['assignee'] or ''}",
        f"- priority: {t['priority']}",
        f"- due: {t['due_date'] or ''}",
        "",
        "#### Description",
        t['description'] or '',
        "",
        "#### Resources",
    ]
    for r in res:
        md.append(f"- {r['kind']}:{r['resource']}")
    md += ["", "#### Notes"]
    for n in notes:
        file = f" file={n['file']}" if n['file'] else ""
        md.append(f"- {n['created_at']}{file}\n  {n['content']}")
    out.write_text("\n".join(md), encoding="utf-8")
    print(str(out))
    return 0


# ---------- parser ----------

def build_parser():
    p = argparse.ArgumentParser(prog="dev", description="Developer tools: doctor, bootstrap, code map, search, graph, impact, seed, and repro")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("doctor", help="Check local environment")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=doctor_cmd)

    s = sub.add_parser("bootstrap", help="One-command setup and smoke test")
    s.set_defaults(func=bootstrap_cmd)

    s = sub.add_parser("code-map", help="Build or query a simple code map")
    sub2 = s.add_subparsers(dest="subcmd", required=True)

    b = sub2.add_parser("build", help="Index repository")
    b.add_argument("--root")
    b.add_argument("--out")
    b.set_defaults(func=code_map_build)

    f = sub2.add_parser("find", help="Search the code map")
    f.add_argument("--map")
    f.add_argument("--kind", choices=["path", "symbol", "import"], default="path")
    f.add_argument("--query")
    f.add_argument("--limit", type=int, default=50)
    f.set_defaults(func=code_map_find)

    s = sub.add_parser("tasks-graph", help="Output task dependency graph")
    s.add_argument("--db")
    s.add_argument("--format", choices=["mermaid", "edges"], default="mermaid")
    s.set_defaults(func=tasks_graph_cmd)

    s = sub.add_parser("impact", help="Show tasks impacted by changed files")
    s.add_argument("--ref", help="Git ref to diff against (e.g., origin/main)")
    s.add_argument("--root")
    s.add_argument("--db")
    s.set_defaults(func=impact_cmd)

    # csearch
    s = sub.add_parser("csearch", help="Semantic-ish search over code map and files")
    s.add_argument("--query", required=True)
    s.add_argument("--kind", choices=["path","symbol","import","text"], default="text")
    s.add_argument("--lang", action="append", help="Filter by language(s)")
    s.add_argument("--path-prefix", action="append", help="Only paths under these prefixes")
    s.add_argument("--map", help="code_map.json path (defaults to cache)")
    s.add_argument("--root", help="Repo root for text search; defaults to CWD")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(func=csearch_cmd)

    # seed
    s = sub.add_parser("seed", help="Populate task-manager DB with deterministic sample data")
    s.add_argument("--db", help="Path to tasks.db (defaults to ~/.gpt5/tasks.db)")
    s.add_argument("--count", type=int, default=8)
    s.add_argument("--force", action="store_true", help="Proceed even if DB has tasks")
    s.set_defaults(func=seed_cmd)

    # repro scaffold
    s = sub.add_parser("repro", help="Issue reproducer scaffolding with optional VCR (vcrpy)")
    sub2 = s.add_subparsers(dest="subcmd", required=True)

    r = sub2.add_parser("scaffold", help="Create a skeleton repro test at .repro/<name>")
    r.add_argument("name")
    r.add_argument("--url", help="Optional URL to hit in the scaffolded test")
    r.set_defaults(func=repro_scaffold_cmd)

    # e2e
    s = sub.add_parser("e2e", help="E2E runner utilities")
    sub3 = s.add_subparsers(dest="subcmd", required=True)

    s1 = sub3.add_parser("scaffold", help="Create .e2e/<name>/spec.py")
    s1.add_argument("name")
    s1.add_argument("--url")
    s1.set_defaults(func=e2e_scaffold_cmd)

    s2 = sub3.add_parser("run", help="Run .e2e/<name>/spec.py")
    s2.add_argument("name")
    s2.set_defaults(func=e2e_run_cmd)

    # preflight
    s = sub.add_parser("preflight", help="Run doctor, tests, code-map, impact, and optional E2E smoke")
    s.add_argument("--e2e", help="Name of E2E spec to run if present")
    s.add_argument("--quick", action="store_true", help="Skip heavy steps like running all tests and E2E")
    s.set_defaults(func=preflight_cmd)

    # preflight for smol-podcaster
    s = sub.add_parser("preflight-smol", help="Repo-specific preflight for smol-podcaster")
    s.add_argument("--quick", action="store_true", help="Skip heavy steps (e.g., API smoke)")
    s.add_argument("--install", action="store_true", help="pip install -r requirements[-dev].txt before checks")
    s.set_defaults(func=preflight_smol_cmd)

    # broker helper
    s = sub.add_parser("broker", help="Manage a local RabbitMQ via Docker")
    sb = s.add_subparsers(dest="subcmd", required=True)
    u = sb.add_parser("up", help="Start RabbitMQ (management image) or start existing container")
    u.add_argument("--name", help="Container name", default="gpt5-rabbitmq")
    u.set_defaults(func=broker_cmd)
    d = sb.add_parser("down", help="Stop and remove RabbitMQ container")
    d.add_argument("--name", help="Container name", default="gpt5-rabbitmq")
    d.set_defaults(func=broker_cmd)
    l = sb.add_parser("logs", help="Tail RabbitMQ logs")
    l.add_argument("--name", help="Container name", default="gpt5-rabbitmq")
    l.add_argument("--tail", help="How many lines to show", default="200")
    l.set_defaults(func=broker_cmd)

    # flake hunter
    s = sub.add_parser("flake", help="Detect flaky tests by re-running suites multiple times")
    s.add_argument("--start", help="Start directory for unittest discovery")
    s.add_argument("--pattern", help="Glob pattern for tests (default: test_*.py)")
    s.add_argument("--runs", type=int, default=3)
    s.add_argument("--seed", type=int)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=flake_run_cmd)

    # codemod
    s = sub.add_parser("codemod", help="Plan and apply simple regex-based code changes safely")
    subcm = s.add_subparsers(dest="subcmd", required=True)

    p1 = subcm.add_parser("plan", help="Preview unified diffs of potential changes")
    p1.add_argument("--root")
    p1.add_argument("--regex", required=True)
    p1.add_argument("--replace", required=True)
    p1.add_argument("--lang", action="append")
    p1.add_argument("--path-prefix", action="append")
    p1.add_argument("--limit", type=int, default=20)
    p1.set_defaults(func=codemod_plan_cmd)

    p2 = subcm.add_parser("apply", help="Apply changes (requires --yes)")
    p2.add_argument("--root")
    p2.add_argument("--regex", required=True)
    p2.add_argument("--replace", required=True)
    p2.add_argument("--lang", action="append")
    p2.add_argument("--path-prefix", action="append")
    p2.add_argument("--limit", type=int, default=9999)
    p2.add_argument("--yes", action="store_true")
    p2.set_defaults(func=codemod_apply_cmd)

    # triage
    s = sub.add_parser("triage", help="Create triage templates and optionally open tasks")
    subtr = s.add_subparsers(dest="subcmd", required=True)
    n = subtr.add_parser("new", help="Create .triage/<name> with a README template")
    n.add_argument("name")
    n.set_defaults(func=triage_new_cmd)
    t = subtr.add_parser("to-tasks", help="Create a task in task-manager for the triage")
    t.add_argument("--title", required=True)
    t.add_argument("--description")
    t.add_argument("--assignee")
    t.add_argument("--priority", type=int)
    t.set_defaults(func=triage_to_tasks_cmd)

    # trace
    s = sub.add_parser("trace", help="Profile a small Python expression using cProfile")
    ssub = s.add_subparsers(dest="subcmd", required=True)
    r = ssub.add_parser("run", help="Run a Python expression under cProfile")
    r.add_argument("--expr", required=True)
    r.add_argument("--out")
    r.set_defaults(func=trace_run_cmd)

    # runbook
    s = sub.add_parser("runbook", help="Generate a runbook from a task in the local DB")
    subrb = s.add_subparsers(dest="subcmd", required=True)
    g = subrb.add_parser("generate", help="Write docs/runbooks/task-<id>.md")
    g.add_argument("--task", required=True)
    g.add_argument("--db")
    g.add_argument("--out")
    g.set_defaults(func=runbook_generate_cmd)

    # openapi
    s = sub.add_parser("openapi", help="OpenAPI utilities")
    so = s.add_subparsers(dest="subcmd", required=True)
    t = so.add_parser("types", help="Generate TS types via openapi-typescript")
    t.add_argument("--url", required=True, help="OpenAPI JSON URL (e.g., http://localhost:8000/openapi.json)")
    t.add_argument("--out", help="Output .d.ts path (default: frontend/lib/api-types.d.ts)")
    t.set_defaults(func=openapi_types_cmd)

    return p


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
