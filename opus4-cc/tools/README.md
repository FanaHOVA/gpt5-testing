# SWE-Lancer Productivity Tools Suite

A comprehensive suite of tools designed to maximize productivity when solving real-world software engineering tasks from the SWE-Lancer benchmark ($250-$32,000 task value range).

## 🚀 Overview

This toolkit provides specialized tools for different aspects of software engineering tasks:

1. **Context Analyzer** - Rapidly understand codebases with tech stack detection and dependency mapping
2. **Cross-Platform Test Generator** - Generate E2E tests for web, iOS, Android, and desktop
3. **Implementation Proposal Analyzer** - Evaluate freelancer proposals with scoring and ROI analysis
4. **Full-Stack Change Impact Analyzer** - Trace changes across database, API, and frontend layers
5. **Bug Pattern Recognition Engine** - Match bugs to known patterns and suggest proven fixes
6. **Security & Permission Auditor** - Comprehensive security scanning and vulnerability detection
7. **Multi-Platform Feature Implementer** - Coordinate feature implementation across platforms
8. **API Integration Assistant** - Streamline API integrations with client generation
9. **Performance Optimization Toolkit** - Identify and fix performance bottlenecks
10. **Task Complexity Estimator** - Estimate effort based on task value and complexity

## 📦 Installation

All tools are standalone Python scripts that can be run directly:

```bash
# Make all tools executable
chmod +x tools/*.py

# Add to PATH for easy access
export PATH="$PATH:/path/to/task-manager/tools"
```

## 🔧 Individual Tool Usage

### Context Analyzer
```bash
# Analyze current directory
./context_analyzer.py

# Analyze specific project
./context_analyzer.py /path/to/project

# Generate JSON report
./context_analyzer.py --output report.json --format json
```

### Cross-Platform Test Generator
```bash
# Create sample test specification
./cross_platform_test_gen.py --create-sample

# Generate tests for all platforms
./cross_platform_test_gen.py --spec sample_test_spec.yaml

# Generate for specific platform
./cross_platform_test_gen.py --spec tests.yaml --platform ios
```

### Bug Pattern Recognition Engine
```bash
# Interactive bug analysis
./bug_pattern_engine.py --interactive

# Analyze bug from JSON
./bug_pattern_engine.py --analyze bug.json

# Show all patterns
./bug_pattern_engine.py --show-patterns
```

### Security Auditor
```bash
# Full security audit
./security_auditor.py /path/to/project

# Filter by severity
./security_auditor.py --severity critical

# Generate detailed report
./security_auditor.py --format detailed --output security-report.json
```

### Performance Optimizer
```bash
# Analyze performance issues
./performance_optimizer.py /path/to/project

# Profile specific Python file
./performance_optimizer.py --profile script.py

# Apply automatic fixes
./performance_optimizer.py --fix
```

### Task Complexity Estimator
```bash
# Estimate single task
./task_complexity_estimator.py --task "Fix API bug" --value 500

# Analyze task portfolio
./task_complexity_estimator.py --portfolio tasks.json

# Run demo analysis
./task_complexity_estimator.py --demo
```

## 🎯 Integrated Toolkit Usage

The `swe_lancer_toolkit.py` provides integrated analysis using multiple tools:

```bash
# Analyze a task from task manager
./swe_lancer_toolkit.py --task 123

# Run specific analysis
./swe_lancer_toolkit.py --analyze security --project /path/to/project

# Generate comprehensive report
./swe_lancer_toolkit.py --task 123 --output report.md --update-task
```

## 📊 Task Manager Integration

All tools integrate with the task manager for coordinated execution:

```bash
# Add a new task
./tm add "Fix double API call bug" -p high -f src/api.js

# Analyze the task with toolkit
./tools/swe_lancer_toolkit.py --task 1 --update-task

# View analysis results
./tm show 1
```

## 🔄 Workflow Examples

### Bug Fix Workflow ($250-$1000)
```bash
# 1. Analyze codebase context
./context_analyzer.py

# 2. Identify bug pattern
./bug_pattern_engine.py --interactive

# 3. Check impact
./impact_analyzer.py --git-diff

# 4. Generate tests
./cross_platform_test_gen.py --spec bug_test.yaml
```

### Feature Implementation Workflow ($5000-$16000)
```bash
# 1. Estimate complexity
./task_complexity_estimator.py --task "Video playback" --value 16000

# 2. Plan multi-platform implementation
./multi_platform_feature.py --demo

# 3. Analyze security requirements
./security_auditor.py

# 4. Generate API clients
./api_integration_assistant.py --spec api.yaml --generate python
```

### Performance Optimization Workflow
```bash
# 1. Profile performance
./performance_optimizer.py

# 2. Analyze bundle size
./performance_optimizer.py --analyze bundle

# 3. Check impact of optimizations
./impact_analyzer.py --changes-file optimizations.json
```

## 🏆 Best Practices

1. **Start with Context**: Always run `context_analyzer.py` first to understand the codebase
2. **Estimate Early**: Use `task_complexity_estimator.py` to calibrate effort
3. **Security First**: Run `security_auditor.py` before deploying any changes
4. **Test Everything**: Use `cross_platform_test_gen.py` to ensure comprehensive testing
5. **Track Impact**: Use `impact_analyzer.py` to understand ripple effects

## 📈 ROI Optimization

The toolkit helps maximize ROI on SWE-Lancer tasks:

- **$250-$500 tasks**: Focus on `bug_pattern_engine.py` for quick fixes
- **$500-$5000 tasks**: Use `proposal_analyzer.py` to evaluate approaches
- **$5000+ tasks**: Full toolkit analysis with `swe_lancer_toolkit.py`

## 🔍 Troubleshooting

### Import Errors
```bash
# Ensure Python path includes tools directory
export PYTHONPATH="$PYTHONPATH:/path/to/task-manager/tools"
```

### Permission Denied
```bash
# Make scripts executable
chmod +x tools/*.py
```

### Missing Dependencies
```bash
# Install required packages
pip install pyyaml
```

## 🤝 Contributing

To add new tools to the suite:

1. Create a new Python script in the `tools/` directory
2. Follow the existing tool structure with CLI interface
3. Add integration to `swe_lancer_toolkit.py`
4. Update this README with usage examples

## 📄 License

These tools are part of the SWE-Lancer productivity suite for solving real-world software engineering tasks efficiently.