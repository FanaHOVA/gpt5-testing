### Reproducer: login-bug

Files:
- test_repro.py: unittest that optionally uses vcrpy if available
- cassettes/repro.yaml: created on first run if vcrpy is installed

Usage:
1) Optional: pip install vcrpy requests
2) python3 -m unittest /Users/alessiofanelli/self-improving/gpt5/.repro/login-bug/test_repro.py

Note: Without vcrpy, the test will not perform HTTP; it still executes and passes.
