# Establishing codebase consistency rules
_Exported on [DATE REDACTED] at 15:43:39 PDT from Cursor (1.3.9)_

---

**User**

You are an AI Engineer agent with the ability to spin up many instances of yourself in parallel. Sometimes it leads to inconsistent code styles and approaches, which make it hard to maintain the codebase in the long run.

Every codebase you work in has explicit and implicit rules on how to write code. Your job is to analyze a codebase and extract different heuristics on how code should be written. You should then formalize it within a set of rules that can be automatically be checked against in the future. 

For things like linting, types, etc you can rely on existing popular tools like ESLint, Rubocop, etc depending on the language you are working in. Remember that these systems often allow you to create custom rules, so take advantage of that.

For more qualitative things, you can look at tools like https://danger.systems/, or even build your own tool for it. This would include rules like keeping controllers slim and isolating their logic to service objects, making sure we always have an index in a column that expects high query volume, etc.

Given that you will be doing this task across many codebases, start by creating a thorough plan document using Markdown that you can give your future self when presented with a new codebase to work with.  Do not refer to other files in this folder.

---

**Cursor**



Of course. Here is a thorough, reusable plan for analyzing codebases to extract and formalize coding heuristics. I will save this as a new Markdown document that you can use as a playbook for future tasks.

I'll start by creating the `CODEBASE_ANALYSIS_PLAYBOOK.md` file in the `pro2-5/codebase-analyzer/` directory.

```markdown
# Codebase Analysis Playbook for Heuristics Extraction

## 1. Objective

The goal of this playbook is to provide a systematic process for analyzing any given codebase, identifying its explicit and implicit coding patterns, and formalizing these heuristics into a set of automated checks.

This ensures that as a codebase evolves—especially with multiple AI and human engineers working in parallel—it remains consistent, maintainable, and adheres to high-quality standards.

## 2. Phase 1: Initial Codebase Exploration

**Goal:** Achieve a high-level understanding of the project's architecture, dependencies, and existing standards.

**Steps:**

1.  **Identify Project Vitals:**
    *   **Languages & Frameworks:** Determine the primary programming languages, frameworks (e.g., React, Rails, Django), and major libraries.
    *   **Dependencies:** Review package manager files (`package.json`, `Gemfile`, `requirements.txt`, `pom.xml`) to understand the project's dependencies.
    *   **Project Structure:** Map out the directory structure to identify the architectural pattern (e.g., Monolith, Microservices, MVC, Layered). Look for key directories like `src/`, `app/`, `pkg/`, `lib/`, `controllers/`, `services/`, and `models/`.

2.  **Analyze Existing Tooling & CI/CD:**
    *   **Linters & Formatters:** Locate existing configurations for tools like ESLint (`.eslintrc.js`), Rubocop (`.rubocop.yml`), Prettier (`.prettierrc`), or Black (`pyproject.toml`). These are the most explicit source of coding standards.
    *   **CI/CD Pipeline:** Examine CI/CD configuration files (e.g., `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`). This reveals the automated checks already in place, such as testing, linting, building, and deployment procedures.

3.  **Review Documentation:**
    *   Thoroughly read `README.md`, `CONTRIBUTING.md`, and any files in `docs/` or an associated wiki. These often contain explicit guidelines on architecture, conventions, and setup.

4.  **Trace a Key Feature:**
    *   Follow a core feature's execution path. For example, trace an API request from the router, through the controller, to a service object, down to the database model, and back. This provides invaluable insight into how components interact in practice.

## 3. Phase 2: Heuristic Identification

**Goal:** Systematically discover and categorize coding patterns to turn them into rules.

### A. Code Style & Formatting (The "Look")

*   **How to Identify:** Look for consistency in naming conventions, spacing, indentation, and overall code structure. Review existing linter configs. If none exist, observe the dominant style in the codebase.
*   **Examples:**
    *   `camelCase` vs. `snake_case` for variables and functions.
    *   `PascalCase` for classes and components.
    *   Hard line-length limits.
*   **Formalization:** Configure a standard linter (ESLint, Rubocop, etc.) with a popular base configuration (e.g., Airbnb, StandardJS) and customize it.

### B. Architectural Patterns (The "Structure")

*   **How to Identify:** Analyze how responsibilities are divided. Where does business logic reside? How is data access abstracted? Are controllers "slim"?
*   **Examples:**
    *   **Slim Controllers:** Controller methods should only handle request/response logic, delegating business logic to service objects.
    *   **Service Layer:** Business logic is encapsulated in service objects, interactors, or use cases.
    *   **Repository Pattern:** Data access is abstracted away from business logic.
*   **Formalization:**
    *   Write custom linter rules (e.g., forbid database imports in controller files).
    *   Use a tool like [Danger](https://danger.systems/) to create PR-level checks.
        *   **Example Rule:** *If a controller file is modified and the line count exceeds a threshold, post a comment suggesting a refactor to a service object.*

### C. Performance & Reliability (The "Guarantees")

*   **How to Identify:** Examine database queries, schema migrations, background job implementations, and external API calls.
*   **Examples:**
    *   **Database Indexing:** Columns used frequently in `WHERE` clauses, `JOIN`s, or for sorting must have a database index.
    *   **N+1 Queries:** Actively prevent N+1 database query patterns.
    *   **API Timeouts:** All external API calls must include a reasonable timeout and retry mechanism.
*   **Formalization:**
    *   **Static Analysis:** Use tools that detect potential N+1 queries (e.g., the `bullet` gem for Rails).
    *   **Custom Scripts:** Write scripts that analyze schema migrations to enforce indexing rules.
    *   **DangerJS:** Add a check to `Dangerfile` to look for new HTTP client usage and verify that a timeout is configured.

### D. Testing Strategy (The "Safety Net")

*   **How to Identify:** Review the `test/` or `spec/` directory. What types of tests are present (unit, integration, E2E)? What is the typical test structure? Are mocks and stubs used consistently?
*   **Examples:**
    *   Every service object must have a corresponding test file.
    *   Prefer recording and replaying real HTTP interactions (e.g., using VCR) over mocking service methods.
    *   A minimum test coverage threshold must be met.
*   **Formalization:**
    *   Integrate a code coverage tool (e.g., Codecov) into the CI pipeline.
    *   Write custom linter rules to enforce test file naming conventions.
    *   Use DangerJS to check if changes to application logic are accompanied by corresponding changes in test files.

## 4. Phase 3: Automation & Integration

**Goal:** Codify the identified heuristics into automated checks that run within the development lifecycle.

1.  **Configure Linters:** Choose and configure the standard linter for the project's language. Document the configuration and commit it to the repository.
2.  **Develop Custom Checks:**
    *   For simple, single-file patterns, write **custom linter rules**.
    *   For complex, cross-file, or architectural patterns, use **DangerJS**. Create a `Dangerfile` to house these rules.
3.  **Integrate into CI/CD:**
    *   Ensure all checks (linting, testing, custom rules) run on every pull request.
    *   Fail the CI build for critical violations.
    *   Use DangerJS to post non-blocking comments for "soft" rules or suggestions, fostering discussion and gradual improvement.

## 5. Phase 4: Documentation & Maintenance

**Goal:** Make the ruleset discoverable, understandable, and adaptable over time.

1.  **Create `CODE_HEURISTICS.md`:**
    *   Create a central document in the repository that lists all formalized rules.
    *   For each rule, provide:
        *   A clear description of the rule.
        *   The reasoning behind it ("Why this is important").
        *   A "Good" and "Bad" code example.
        *   A reference to how the rule is enforced (e.g., "See `.eslintrc.js#my-custom-rule`").
2.  **Establish an Evolution Process:**
    *   Define a process for how the ruleset can be updated. Changes to heuristics should be discussed and approved via pull requests to the configuration files or the `CODE_HEURISTICS.md` document itself.

```

I have created the `CODEBASE_ANALYSIS_PLAYBOOK.md` file with a comprehensive plan. You can find it in the `pro2-5/codebase-analyzer/` directory.

This playbook provides a structured approach for your AI agents to analyze new codebases, identify coding heuristics, and formalize them into automated checks. It covers everything from initial exploration and heuristic identification to automation and long-term maintenance.

You can now give this playbook to your other AI agents as a starting point for this task in any new codebase. Let me know if you have any other questions.


