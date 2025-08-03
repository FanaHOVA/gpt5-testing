# Establishing coding standards for AI projects
_Exported on [DATE REDACTED] at 15:28:54 PDT from Cursor (1.3.9)_

---

**User**

You are an AI Engineer agent with the ability to spin up many instances of yourself in parallel. Sometimes it leads to inconsistent code styles and approaches, which make it hard to maintain the codebase in the long run.

Every codebase you work in has explicit and implicit rules on how to write code. Your job is to analyze a codebase and extract different heuristics on how code should be written. You should then formalize it within a set of rules that can be automatically be checked against in the future. 

For things like linting, types, etc you can rely on existing popular tools like ESLint, Rubocop, etc depending on the language you are working in. Remember that these systems often allow you to create custom rules, so take advantage of that.

For more qualitative things, you can look at tools like https://danger.systems/, or even build your own tool for it. This would include rules like keeping controllers slim and isolating their logic to service objects, making sure we always have an index in a column that expects high query volume, etc.

Given that you will be doing this task across many codebases, start by creating a thorough plan document using Markdown that you can give your future self when presented with a new codebase to work with.  

---

**Cursor**

Planning to add a reusable, thorough Markdown playbook to the repo that outlines a step-by-step process for analyzing any codebase and codifying heuristics into enforceable rules and CI checks. I'll create docs/codebase-analysis-playbook.md with checklists, per-language implementations (ESLint, RuboCop, Danger, Semgrep, etc.), and rollout strategy.

```markdown
## Codebase Analysis & Rule Codification Playbook

A practical, repeatable process to discover a project's explicit and implicit coding heuristics, convert them into enforceable rules, and wire them into CI for continuous governance.

This playbook assumes polyglot monorepos are common and prioritizes automation, DRY enforcement, and incremental rollout.

---

### Outcomes
- A machine-enforceable rule set (linters, type settings, architecture constraints, CI checks).
- A human-readable Rulebook documenting conventions and rationale.
- A stable rollout plan with baselines, allowlists, and ownership.
- Tooling to keep style and design consistent across many contributors/agents.

---

### Quickstart Checklist
- Inventory: languages, frameworks, package managers, CI, test frameworks, infra, DBs.
- Read governing docs: README, CONTRIBUTING, ADRs, CODEOWNERS, lint configs, tsconfig, .rubocop.yml, Dangerfile, pre-commit, editorconfig.
- Detect implicit patterns: folder structure, naming, architecture boundaries, error/logging/test patterns, data model conventions.
- Propose rules: map each heuristic to a check (ESLint/RuboCop/Semgrep/Danger/custom), define severity, scope, exemptions.
- Implement configs + custom rules, add CI gates, keep initial severity to warn with baseline.
- Roll out gradually: fail new/edited code; schedule cleanup of legacy.

---

### Phase 0 — Preparation
- Confirm repository type: mono vs multi-repo; root tooling layout.
- Ensure local reproducibility: package managers locked, language runtimes pinned, container/devbox if needed.
- Establish a working branch just for governance changes.

---

### Phase 1 — Discovery & Inventory
1) Files and configs to read first
- README, CONTRIBUTING, ADRs, STYLEGUIDE, CODEOWNERS, SECURITY.md, PR templates.
- Lint/format/type configs: ESLint/TSConfig/Prettier, RuboCop, ruff/flake8/black/mypy, golangci-lint, ktlint/detekt, SwiftLint.
- Build/CI: GitHub Actions, CircleCI, Buildkite, Dangerfile, pre-commit.
- Test setup: jest/vitest/mocha, RSpec/VCR, pytest, go test, junit, coverage.
- Infra: Dockerfiles, Helm charts, Terraform, Procfiles.

2) Automated inventory (scripts you will run/replicate)
- Language detection: file extensions, lockfiles (package-lock/yarn.lock/pnpm-lock, Gemfile.lock, poetry.lock, go.mod, pom.xml).
- Framework detection: Rails, Next.js/Nuxt, Django/FastAPI, Spring/Quarkus, NestJS.
- Metrics: file counts per type, test-to-src ratio, coverage if available, duplication, average complexity.
- Dependency graph: import trees, cycles, layer violations, dead code.

3) People/process conventions via artifacts
- Branching model, commit message conventions, release/versioning.
- Review/merge policies, protected branches.

Deliverables
- Inventory report (markdown) + initial hypothesis list of heuristics.

---

### Phase 2 — Heuristic Extraction
Focus on patterns that impact maintainability, correctness, and performance.

- Naming and structure
  - Feature-level folder boundaries (e.g., app/models vs app/services; src/features/*).
  - File naming conventions for tests, factories, components.
- Architecture
  - Controllers thin; business logic in services/use-cases.
  - Domain boundaries and allowable dependencies among layers.
  - Public vs internal module APIs.
- Testing
  - Preferred frameworks and stubbing/mocking strategy.
  - HTTP recording approach (e.g., VCR for Ruby; nock/polly for JS).
  - Required tests per change type (units for lib, request/integration for APIs).
- Error handling & Observability
  - Centralized error boundaries, result types/monads, retry policies.
  - Structured logging keys, PII handling, metrics and tracing patterns.
- Security & Secrets
  - Input validation, authz/authn placement, secure headers.
  - Secret management and scanning policies.
- Data/DB
  - Indexing conventions, foreign keys, non-null policy, safe migrations.
  - N+1 prevention, eager load patterns, caching.
- Performance
  - Caching layers, background jobs, rate limits.
- Frontend-specific
  - State management, component hierarchy, styling approach, accessibility rules.

Deliverables
- Heuristic table: heuristic → rationale → evidence → proposed rule/tool → severity.

---

### Phase 3 — Rule Design
For each heuristic, define:
- Rule name and category (style, correctness, architecture, performance, security, process).
- Enforcing tool(s) and rule implementation plan.
- Scope (file, directory, repo-wide, PR-time), enforcement point (pre-commit, push, CI), severity (error/warn/info).
- Auto-fix availability and max churn allowed.
- Exemptions: annotation/comment pattern, allowlist files, expiry date.
- Ownership and metrics: who maintains, how violations are tracked.

Rule taxonomy examples
- Style/format: formatter + linter (Prettier + ESLint, Black + ruff, gofmt + golangci-lint).
- Type strictness: tsconfig strict, mypy strict, nil safety (Sorbet/Kotlin), Go interfaces.
- Architecture: boundaries/import rules, dependency cycles, layering.
- Testing: missing tests for changed modules, disallowed mocks, VCR cassette required for HTTP tests.
- DB: required indexes on foreign keys and high-cardinality columns, migration safety checks.
- Security: secret scanning, dependency audit, dangerous API usage.
- Process: PR size limits, description template, ADR requirement for risky changes.

---

### Phase 4 — Implementation per Stack

JavaScript/TypeScript
- ESLint: base + plugins
  - eslint:recommended, @typescript-eslint/recommended(+strict), import, promise, unicorn, jest/vitest, jsx-a11y (web), security, sonarjs.
  - Architecture: dependency-cruiser or eslint-plugin-boundaries/import/no-restricted-paths for layer rules; no circular deps.
- Formatting: Prettier with eslint-config-prettier.
- Types: tsconfig strict=true, noImplicitAny, noUncheckedIndexedAccess, exactOptionalPropertyTypes, noPropertyAccessFromIndexSignature.
- Tests: jest/vitest lint rules; forbid focused tests; enforce test naming and colocated factories.
- Additional tooling: depcheck/ts-prune for dead exports; semgrep for hard-to-express patterns.
- PR-time checks (Danger):
  - PR description present, size threshold, at least one test file changed when src changed, changelog/ADR for breaking changes.

Ruby / Rails
- RuboCop: rubocop, rubocop-performance, rubocop-rails, rubocop-rspec.
  - Metrics thresholds tuned to project; prefer smaller methods/controllers.
  - Custom cops for "controllers must delegate to services" (detect business logic keywords outside services).
- Testing: RSpec style rules; enforce VCR for external HTTP specs; forbid shoulda-matchers if team standard; prefer explicit expectations.
- Security: brakeman, bundler-audit; forbid OpenStruct in hot paths; frozen string literals.
- DB: strong_migrations, custom Danger rule to enforce indexes in migrations and check NOT NULL + FK presence.

Python
- ruff (superset of flake8), black, isort, mypy (strict optional, tightened gradually), bandit, safety.
- Architecture: import-linter or custom AST checks with libcst; enforce layered imports.
- Pytest rules: forbid bare asserts in non-test; enforce factory/test layout.

Go
- golangci-lint with staticcheck, errcheck, gosimple, revive; gofmt; go vet; gosec.
- Architecture: forbid cross-package imports that break boundaries; enforce interfaces in designated packages.

JVM (Java/Kotlin)
- Checkstyle/ktlint, SpotBugs/Detekt, ErrorProne, NullAway.
- ArchUnit tests to encode architecture/layering rules and package boundaries.

iOS/Swift
- SwiftLint; strict module imports; danger-swift for PR checks.

Cross-language engines
- Semgrep for custom, portable rules; CodeQL for deep security queries.

---

### Phase 5 — CI/CD Integration
- Pre-commit hooks: fast formatters/linters and basic secret scan.
- CI stages: lint → typecheck → test → build → security → rules (danger/semgrep/arch tests) → package.
- Cache intelligently to keep runtimes fast.
- Baseline mode: run linters on changed files only; repo-wide in scheduled weekly job.
- Reporters: SARIF upload for code scanning; annotations on PR.

---

### Phase 6 — Rollout Strategy
- Baseline
  - Record current violations into a baseline file per tool (eslint --max-warnings=∞, ruff --statistics, rubocop --auto-gen-config, semgrep --baseline).
  - Fail on new violations, ignore baseline.
- Staging
  - Start with warn severity in CI; switch to error after 1–2 sprints.
  - Gate only changed files initially; gradually widen scope.
- Exemptions
  - Require justification in code comment or PR; attach expiry date; collect metrics.
- Ownership
  - Assign rule owners; rotate; track violations and time-to-fix.

---

### Phase 7 — Maintenance & Evolution
- Quarterly rule review: adjust thresholds, retire ineffective rules, add new.
- Track KPIs: PR cycle time, defect rate, MTTR, code health metrics, flake rate, build times.
- Document exceptions and their rationale; aim to remove over time.

---

### Qualitative Heuristics → How To Codify

Controllers should be slim
- Metrics rules for max method length/ABC complexity in controller directories.
- Custom checks forbidding data access or business keywords in controllers (ActiveRecord queries, non-trivial branching) unless delegating to services.

Services/use-cases own business logic
- Require entrypoints under services/use_cases with public API; forbid cross-domain imports.
- Danger/Arch rules to ensure controllers only call services.

Indexes for high-volume queries
- Danger CI that parses migrations and flags added columns lacking an index when used in WHERE/JOIN in recent code.
- Semgrep rules to detect frequent query predicates without supporting index annotations.

HTTP external calls recorded in tests
- Enforce VCR or equivalent; Danger checks for :vcr tag or cassette usage in new specs touching HTTP clients.

Avoid N+1 queries
- Semgrep/RuboCop cops to require includes/preload when iterating over associations.
- CI job running a test suite with bullet or query detectors; fail on new bullet warnings.

Logging standards and PII
- Semgrep checks for logging of email, phone, token, id without hashing/redaction.
- Enforce structured logger usage and consistent keys.

Security
- Secret scanning in pre-commit and CI; block high-entropy strings.
- CodeQL or Semgrep security rules; dependency audits in CI.

---

### Rule Authoring Templates (Skeletons)

ESLint custom rule (TypeScript)
```ts
import { TSESTree, ESLintUtils } from '@typescript-eslint/utils';

export const rule = ESLintUtils.RuleCreator(() => 'https://internal/docs')({
  name: 'no-controller-business-logic',
  meta: { type: 'problem', docs: { description: 'Controllers must delegate to services' }, schema: [], messages: { disallow: 'Move business logic to a service.' } },
  defaultOptions: [],
  create(context) {
    const inControllers = context.getFilename().includes('/controllers/');
    return inControllers ? {
      CallExpression(node: TSESTree.CallExpression) {
        // Detect suspicious calls here
        context.report({ node, messageId: 'disallow' });
      },
    } : {};
  },
});
```

RuboCop custom cop
```rb
module RuboCop
  module Cop
    module Project
      class ControllersDelegateToServices < Base
        MSG = 'Move business logic from controllers into services.'
        def on_def(node)
          return unless node.file.include?('/controllers/')
          add_offense(node)
        end
      end
    end
  end
end
```

Danger rule ideas (JavaScript)
```js
// dangerfile.js
import { danger, warn, fail, markdown } from 'danger';

if (!danger.github.pr.body || danger.github.pr.body.length < 20) warn('Please add a meaningful PR description.');

const changedSrc = danger.git.modified_files.filter(f => f.startsWith('src/') || f.startsWith('app/'));
const changedTests = danger.git.modified_files.filter(f => /(__tests__|spec|test)\//.test(f));
if (changedSrc.length > 0 && changedTests.length === 0) warn('Source files changed without accompanying tests.');

if (danger.github.pr.additions + danger.github.pr.deletions > 1200) warn('PR is large; consider splitting.');
```

Semgrep rule (YAML) example
```yaml
rules:
- id: no-pii-logging
  languages: [javascript, typescript, ruby, python]
  message: Possible PII logged; use redaction helpers
  severity: WARNING
  patterns:
  - pattern-either:
    - pattern: console.$METHOD($X)
    - pattern: logger.$METHOD($X)
  - metavariable-pattern:
      metavariable: $X
      patterns:
      - pattern: /email|token|password|ssn/i
```

---

### CI Wiring (GitHub Actions skeleton)
```yaml
name: CI
on: [pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm ci
      - run: npm run lint -- --max-warnings=0
  types:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm ci
      - run: npm run typecheck
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          sudo apt-get update && sudo apt-get install -y ruby-full
          gem install bundler
      - uses: ruby/setup-ruby@v1
        with: { ruby-version: '3.2' }
      - run: bundle install --path vendor/bundle
      - run: bundle exec rspec
  danger:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx danger ci
```

---

### Baseline & Exceptions
- Baseline creation
  - ESLint: eslint . -f json > eslint-baseline.json (then filter changed files only in CI).
  - RuboCop: rubocop --auto-gen-config and commit .rubocop_todo.yml.
  - ruff: ruff --select ALL --statistics to snapshot counts; optionally use noqa: E/W codes selectively.
  - Semgrep: semgrep --baseline-ref main --json > semgrep-baseline.json.
- Exceptions
  - Use inline suppression with reason and expiry, or central allowlist with PR reference.

---

### Deliverables Template
- /rulebook/README.md — Human-readable rules with rationale and examples.
- Tool configs at repo root or per package:
  - .eslintrc.cjs, .prettierrc, tsconfig.json; .rubocop.yml; ruff.toml, pyproject.toml; .semgrep.yml; .github/workflows/*.yml; Dangerfile.
- Custom rules packages (e.g., eslint-plugin-yourorg, rubocop-yourorg).
- Baseline files and exception registry.

---

### Operating Principles
- DRY: prefer org-level shared config/plugins; local overrides only when necessary.
- Local-first fixes; avoid sweeping refactors unless automated and safe.
- Measure impact; tighten thresholds iteratively.
- Keep rules explainable; provide auto-fixes where possible.

---

### Appendix: Useful Tools by Ecosystem
- JS/TS: ESLint, Prettier, TypeScript, dependency-cruiser, ts-prune, depcheck, jest/vitest, nyc/coverage.
- Ruby: RuboCop (+Rails/Performance/RSpec), Brakeman, Bundler Audit, Strong Migrations, Danger.
- Python: ruff, black, isort, mypy, bandit, safety, libcst.
- Go: golangci-lint, staticcheck, gosec, depguard.
- JVM: ArchUnit, ErrorProne, NullAway, ktlint/detekt.
- Cross: Semgrep, CodeQL, pre-commit, GitLeaks/TruffleHog, Danger.

```

### Codebase Analysis & Rule Codification Playbook added

- I added a thorough, reusable playbook to your repo at `docs/codebase-analysis-playbook.md`.
- It covers end-to-end discovery, heuristic extraction, rule design, per-language enforcement (ESLint, RuboCop, ruff/black/mypy, golangci-lint, ArchUnit, SwiftLint), cross-language rules (Semgrep, CodeQL), CI wiring (GitHub Actions/Danger), rollout with baselines, and long-term maintenance.
- No linter issues were found for the new document.

### Highlights

- Purpose-built to keep teams and AI agents aligned on consistent styles and architecture.
- Concrete mapping from qualitative heuristics to enforceable rules (controllers slim → cops/ESLint rules/Danger; DB indexing → Danger/Semgrep; VCR enforcement; boundaries via dependency-cruiser/ArchUnit/import-linter).
- Includes skeletons for:
  - ESLint custom rules (TypeScript)
  - RuboCop custom cops (Ruby)
  - Danger checks (JS)
  - Semgrep rules (YAML)
  - CI skeleton with staged gates and baselines

### What you can do next

- Review and adjust the playbook’s defaults to your org’s preferences (naming, thresholds, plugin selections).
- When you have a target codebase, follow the Phase 1 discovery checklist in the doc to inventory languages, frameworks, and existing tooling.
- Use the “Deliverables Template” to standardize where rule configs and baselines live.
- If you want, I can bootstrap a basic rule set for a specific stack (e.g., Rails + TS monorepo) with shared configs, a `Dangerfile`, and a CI workflow, then stage a rollout using baselines.

