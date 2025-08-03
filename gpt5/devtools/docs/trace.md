### dev trace

Profile a small Python expression using cProfile and emit a .prof file and text summary.

Examples:
```bash
./gpt5/devtools/dev trace run --expr "sum(range(1000000))" --out /tmp/trace.prof
cat /tmp/trace.txt
```

Notes:
- Minimal dependency footprint; swap in py-spy or real tracing later if desired.
