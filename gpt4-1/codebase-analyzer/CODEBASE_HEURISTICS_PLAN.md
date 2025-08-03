# 🧑‍💻 Codebase Heuristics Extraction & Rule Formalization Plan

## 1. **Initial Codebase Survey**

### 1.1. Inventory the Codebase
- List all top-level directories and files.
- Identify main languages, frameworks, and build tools.
- Note presence of configuration files (e.g., `.eslintrc`, `.rubocop.yml`, `pyproject.toml`, `Makefile`, etc.).

### 1.2. Identify Domain-Specific Patterns
- Look for domain-driven design, architectural patterns (MVC, CQRS, etc.).
- Note any custom folder structures or naming conventions.

---

## 2. **Extract Explicit Rules**

### 2.1. Linting & Formatting
- Identify and document all linting tools (ESLint, Rubocop, Flake8, etc.).
- Extract configuration and custom rules from linter config files.
- Note code formatting tools (Prettier, Black, etc.) and their settings.

### 2.2. Typing & Static Analysis
- Check for type systems (TypeScript, MyPy, Sorbet, etc.).
- Document type coverage requirements and enforcement levels.

### 2.3. Testing Conventions
- Identify test frameworks and directory structure.
- Note naming conventions for test files and test cases.
- Document rules for mocking, fixtures, and integration vs. unit tests.

---

## 3. **Extract Implicit/Qualitative Rules**

### 3.1. Code Organization & Architecture
- How are controllers, services, models, and utilities separated?
- Are there rules about keeping controllers slim, using service objects, etc.?
- Is business logic isolated from I/O and framework code?

### 3.2. Performance & Scalability
- Are there conventions for indexing database columns?
- Are there patterns for caching, batching, or rate-limiting?

### 3.3. Security & Compliance
- Are there rules for input validation, escaping, or authentication?
- Is sensitive data handling (e.g., secrets, PII) standardized?

### 3.4. Documentation & Comments
- Are docstrings or comments required for public APIs?
- Is there a standard for README or in-code documentation?

### 3.5. Dependency Management
- Are there rules for updating dependencies, pinning versions, or using lockfiles?

---

## 4. **Formalize Rules for Automation**

### 4.1. Linting & Formatting
- Ensure all linter/formatter rules are codified in config files.
- Add or update custom rules as needed.

### 4.2. Static Analysis & Type Checking
- Enforce type coverage thresholds.
- Add CI checks for type errors.

### 4.3. Custom Qualitative Rules
- Use tools like [Danger](https://danger.systems/) to enforce PR-level rules (e.g., changelog updates, test coverage, documentation).
- For Ruby: Add custom Rubocop cops.
- For JS/TS: Add custom ESLint rules.
- For Python: Use flake8 plugins or write custom scripts.

### 4.4. Build Your Own Rule Checker (if needed)
- For rules not covered by existing tools, create a custom script or tool.
- Integrate with CI to block merges on violations.

---

## 5. **Document & Communicate the Rules**

### 5.1. Write a Rules Manifest
- Create a `CODE_QUALITY_RULES.md` or similar document.
- List all rules, rationale, and enforcement mechanism (linter, Danger, custom script, etc.).
- Provide examples of compliant and non-compliant code.

### 5.2. Onboarding & Enforcement
- Add documentation to onboarding guides.
- Ensure CI/CD enforces all rules.
- Periodically review and update rules as the codebase evolves.

---

## 6. **Continuous Improvement**

- Regularly review code reviews and PRs for new implicit rules or anti-patterns.
- Update automated checks and documentation accordingly.
- Encourage team to propose new rules as the codebase grows.

---

## 📋 **Checklist for New Codebase Analysis**

- [ ] Inventory codebase structure and tools
- [ ] Extract all explicit linter, formatter, and type rules
- [ ] Identify implicit architectural and qualitative rules
- [ ] Formalize rules in config files and/or custom scripts
- [ ] Document all rules and enforcement mechanisms
- [ ] Integrate checks into CI/CD
- [ ] Review and update rules regularly

---

## 🛠️ **Recommended Tools**

- **Linting:** ESLint, Rubocop, Flake8, etc.
- **Formatting:** Prettier, Black, Rubocop, etc.
- **Type Checking:** TypeScript, MyPy, Sorbet, etc.
- **Qualitative Checks:** Danger, custom scripts, custom linter plugins
- **CI Integration:** GitHub Actions, CircleCI, Travis, etc.

---

## Example: Custom Rule with Danger

```ruby
# Dangerfile
fail("Add a test for new features!") if git.modified_files.grep(/\.rb$/).any? && !git.modified_files.grep(/_spec\.rb$/).any?
```

---

By following this plan, you will ensure that every codebase you work on is analyzed thoroughly, and that both explicit and implicit rules are formalized, documented, and enforced for long-term maintainability and quality.