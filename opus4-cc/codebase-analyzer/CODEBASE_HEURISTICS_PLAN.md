## Alessio's note: This is the same for both Claude Code and Cursor. Given that it's a text-only document, I didn't generate it twice as the different harness wouldn't make a difference.

# Codebase Heuristics Extraction Plan

## Overview
This document provides a systematic approach for analyzing codebases to extract coding patterns, conventions, and implicit rules, then formalizing them into automated checks. The goal is to maintain consistency across large codebases, especially when multiple AI instances or developers work in parallel.

## Phase 1: Initial Codebase Analysis

### 1.1 Technology Stack Identification
- [ ] Identify primary language(s)
- [ ] List frameworks and major libraries
- [ ] Note build tools and package managers
- [ ] Document testing frameworks
- [ ] Identify existing linting/formatting tools

### 1.2 Project Structure Analysis
```bash
# Generate project structure overview
find . -type f -name "*.{js,ts,py,rb,java,go}" | head -50
find . -type d -name "test*" -o -name "spec*" -o -name "__tests__"
```

### 1.3 Configuration Files Audit
- [ ] `.eslintrc`, `.rubocop.yml`, `pyproject.toml`, etc.
- [ ] `.editorconfig`, `.prettierrc`
- [ ] CI/CD configuration files
- [ ] Pre-commit hooks
- [ ] Custom linting rules already in place

## Phase 2: Pattern Discovery

### 2.1 Architectural Patterns
Analyze the codebase for:

#### MVC/MVP/MVVM Patterns
- Controller thickness (LOC, number of methods)
- Service object usage patterns
- Model responsibility boundaries
- View logic isolation

#### Modularization Patterns
- Module size and complexity
- Dependency patterns
- Interface definitions
- Package/namespace organization

### 2.2 Code Style Patterns

#### Naming Conventions
```
# Extract common patterns
- Variable naming: camelCase vs snake_case
- File naming conventions
- Class/Function naming patterns
- Test file naming conventions
```

#### Import/Require Patterns
- Import grouping and ordering
- Absolute vs relative imports
- Barrel exports usage
- Circular dependency avoidance

### 2.3 Data Access Patterns

#### Database Interactions
- Query patterns (N+1 detection)
- Index usage on foreign keys
- Migration patterns
- Connection pooling practices

#### API Patterns
- Error handling consistency
- Response format standards
- Authentication/authorization patterns
- Rate limiting implementation

### 2.4 Testing Patterns

#### Test Structure
- Test file organization
- Test naming conventions
- Setup/teardown patterns
- Mocking vs integration approaches

#### Coverage Patterns
- Minimum coverage thresholds
- Critical path identification
- Edge case handling

## Phase 3: Rule Categorization

### 3.1 Severity Levels
1. **Critical**: Security vulnerabilities, data loss risks
2. **High**: Performance issues, maintainability blockers
3. **Medium**: Code clarity, team conventions
4. **Low**: Style preferences, nice-to-haves

### 3.2 Rule Types

#### Syntactic Rules (Tool-enforceable)
- Linting rules (ESLint, Rubocop, Pylint)
- Type checking (TypeScript, Flow, mypy)
- Formatting (Prettier, Black, gofmt)

#### Semantic Rules (Custom tools needed)
- Business logic patterns
- Architectural constraints
- Performance patterns
- Security patterns

#### Documentation Rules
- Comment requirements
- API documentation standards
- README completeness
- Changelog maintenance

## Phase 4: Implementation Strategy

### 4.1 Existing Tool Configuration

#### Language-Specific Tools
```javascript
// ESLint custom rules example
module.exports = {
  rules: {
    'no-direct-db-access-in-controllers': require('./rules/no-direct-db-access'),
    'require-index-on-foreign-keys': require('./rules/require-index')
  }
};
```

```ruby
# Rubocop custom cops example
class ServiceObjectNaming < RuboCop::Cop::Base
  MSG = 'Service objects should end with "Service"'
  
  def on_class(node)
    # Implementation
  end
end
```

### 4.2 Danger.js Integration

```javascript
// dangerfile.js
import { danger, warn, fail } from 'danger';

// Controller complexity check
const controllerFiles = danger.git.modified_files.filter(f => f.includes('controller'));
controllerFiles.forEach(file => {
  const diff = danger.git.diffForFile(file);
  const lineCount = diff.added.split('\n').length;
  
  if (lineCount > 50) {
    warn(`Controller ${file} has ${lineCount} new lines. Consider extracting to service objects.`);
  }
});

// Database migration checks
const migrationFiles = danger.git.modified_files.filter(f => f.includes('migration'));
if (migrationFiles.length > 0) {
  warn('New migration detected. Ensure indexes are added for foreign keys.');
}
```

### 4.3 Custom Tool Development

#### Rule Engine Architecture
```python
class RuleEngine:
    def __init__(self):
        self.rules = []
    
    def register_rule(self, rule):
        self.rules.append(rule)
    
    def analyze(self, codebase_path):
        violations = []
        for rule in self.rules:
            violations.extend(rule.check(codebase_path))
        return violations

class Rule(ABC):
    @abstractmethod
    def check(self, path):
        pass
```

## Phase 5: Documentation and Maintenance

### 5.1 Rule Documentation Template
```markdown
## Rule: [Rule Name]

**Category**: Architecture | Performance | Security | Style
**Severity**: Critical | High | Medium | Low
**Automated**: Yes | No | Partial

### Description
[What this rule checks for]

### Rationale
[Why this rule exists]

### Good Example
```[language]
// Code that follows the rule
```

### Bad Example
```[language]
// Code that violates the rule
```

### How to Fix
[Steps to resolve violations]

### Exceptions
[When this rule can be ignored]
```

### 5.2 Progressive Rollout

1. **Phase 1**: Warning-only mode
2. **Phase 2**: Blocking for new code only
3. **Phase 3**: Gradual fixing of existing violations
4. **Phase 4**: Full enforcement

## Phase 6: Execution Checklist

### Initial Analysis (Day 1)
- [ ] Run codebase statistics tool
- [ ] Analyze top 10 most changed files
- [ ] Review recent PRs for patterns
- [ ] Interview team (if available) or analyze PR comments
- [ ] Document initial findings

### Pattern Extraction (Day 2-3)
- [ ] Categorize discovered patterns
- [ ] Prioritize by impact and frequency
- [ ] Create rule prototypes
- [ ] Test rules on sample code

### Implementation (Day 4-5)
- [ ] Configure existing tools
- [ ] Write custom rules
- [ ] Set up Danger.js or equivalent
- [ ] Create CI/CD integration
- [ ] Document all rules

### Validation (Day 6)
- [ ] Run full codebase scan
- [ ] Review violations
- [ ] Adjust rule sensitivity
- [ ] Create fixing guide
- [ ] Set up monitoring

## Appendix: Tool-Specific Configurations

### ESLint Plugin Development
```bash
npm init @eslint/plugin@latest
```

### Rubocop Custom Cop
```bash
bundle exec rubocop --init
```

### Python Custom Linter
```bash
pip install ast astroid
```

### Danger.js Setup
```bash
npm install --save-dev danger
```

## Metrics for Success

1. **Consistency Score**: % of code following established patterns
2. **Violation Trends**: Decreasing violations over time
3. **Developer Satisfaction**: Survey on code quality
4. **Review Time**: Reduction in PR review cycles
5. **Bug Density**: Correlation with defect rates

## Common Pitfalls to Avoid

1. **Over-engineering**: Don't create rules for one-off cases
2. **Too Strict**: Allow for reasonable exceptions
3. **Poor Communication**: Ensure team buy-in
4. **Lack of Context**: Consider business requirements
5. **No Gradual Adoption**: Avoid big-bang approaches

---

**Remember**: The goal is sustainable code quality, not perfection. Focus on rules that provide the most value with the least friction.