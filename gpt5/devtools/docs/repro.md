### dev repro scaffold

Create a minimal, deterministic test skeleton under `.repro/<name>` that can optionally record HTTP using `vcrpy`.

What it generates:
- test_repro.py: a unittest that, if `vcrpy` is available, records one HTTP call to a cassette; otherwise it executes a trivial assertion
- cassettes/repro.yaml: created on first run when `vcrpy` is installed

Example:
```bash
./gpt5/devtools/dev repro scaffold login-bug --url https://httpbin.org/get
python3 -m unittest .repro/login-bug/test_repro.py
```

Notes:
- Optional deps: `pip install vcrpy requests`
- Safe to commit the scaffold; cassettes can be committed for determinism or ignored per project policy.
