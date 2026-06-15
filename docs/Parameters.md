# Engineering Impact Dashboard Parameters

## Working thesis

The dashboard should not rank engineers by raw activity. The goal is to identify engineers who make the codebase and engineering process healthier.

The strongest angle for this assessment is:

> Impactful engineers ship intentional, reviewable changes that are easy to understand, remain healthy after merge, and improve the team's ability to build safely.

This means the dashboard should focus on three core ideas:

1. PR Reviewability
2. Developer Intent
3. Post-Merge Code Health

Other supporting dimensions should be included to make the ranking feel complete, but the dashboard should make the above three ideas the signature feature.

---

## Core scoring model

| Priority | Dimension | Suggested Weight | Simple Question | Why It Matters |
|---:|---|---:|---|---|
| 1 | PR Reviewability and Developer Intent | 30% | Was the change focused, intentional, and easy to review? | This is the most distinctive signal. It detects noisy diffs, oversized PRs, unnecessary rewrites, and AI-style churn. |
| 2 | Code Ownership and Post-Merge Health | 25% | What happened after the code was merged? | This goes beyond merge-time activity and asks whether the change stayed stable or caused follow-up churn. |
| 3 | Requirement-Aligned Test Quality | 15% | Do the tests prove the actual requirement or bug fix? | This avoids rewarding meaningless coverage and focuses on tests that protect behavior. |
| 4 | Simplicity, Readability, and Design Quality | 15% | Did the engineer make the code easier to understand and maintain? | Great engineers reduce complexity, not just add code. |
| 5 | Engineering Process Influence | 5% | Did the engineer improve the work through review, design input, or clarification? | Captures non-code engineering impact. |
| 6 | Issue Discovery, Triage, and Resolution | 5% | Did the engineer help the team find, understand, prioritize, and resolve problems? | Issues show the problem-solving layer before and after PRs. |
| 7 | Dependency and Duplication Hygiene | 5% | Did the engineer keep the codebase lean and avoid unnecessary maintenance burden? | Detects bloat, duplicate logic, and unnecessary dependencies. |

Total: 100%

---

## Dimension 1: PR Reviewability and Developer Intent

### Definition

This dimension measures whether an engineer submits changes that are focused, intentional, and safe to review. A good PR should make it clear what changed, why it changed, and how reviewers can validate it.

This is not the same as rewarding small PRs. Some important work is naturally large. The goal is to reward PRs that are appropriately scoped and penalize PRs that mix unrelated changes, noisy rewrites, formatting churn, and unnecessary movement.

### Main idea

> We do not just measure how much code changed. We measure whether the diff was intentional and reviewable.

### Metrics

| Metric | What It Measures | Positive Signal | Negative Signal | Possible GitHub Evidence |
|---|---|---|---|---|
| Manageable PR size | Whether a PR is small enough to review safely | Small or medium focused PRs, or large PRs with clear structure | Huge PRs with no clear review path | Additions, deletions, changed files, PR description |
| Scope focus | Whether the PR solves one clear problem | Files and changes align with one purpose | Bugfix plus refactor plus formatting plus unrelated cleanup | PR title, description, labels, changed paths |
| Diff intent clarity | Whether the reason for the diff is clear | PR explains why changes were made | Large diff with vague title or no description | PR body, linked issue, review comments |
| Low noisy-churn ratio | Whether changes are meaningful instead of mechanical | Functional changes are easy to isolate | Renames, formatting, moving functions around with little value | File diffs, review comments, repeated delete/add blocks |
| Mechanical and functional separation | Whether formatting or generated changes are separated from logic | Dedicated cleanup PRs or clearly separated commits | Formatting mixed into feature or bugfix logic | Changed files, commit messages, PR body |
| Review friction | Whether reviewers struggled to understand or review the PR | Few clarification comments, focused review | Reviewers ask to split, simplify, explain, or reduce scope | PR review comments, issue comments |
| AI-style low-signal rewrite detection | Whether code was rewritten without meaningful behavior change | Small targeted changes | Rewriting entire functions for tiny changes, unnecessary variable renames | Similar old/new blocks, diff patterns, review comments |
| Reviewability explanation | Whether the author helps reviewers navigate the PR | PR includes testing notes, screenshots, migration notes, risk notes | No validation details for risky changes | PR body, checklist, linked issue |

### Suggested scoring

| Sub-score | Suggested Weight Inside Dimension |
|---|---:|
| PR size appropriateness | 20% |
| Scope focus | 20% |
| Diff intent clarity | 20% |
| Low noisy churn | 20% |
| Review friction | 10% |
| Testing and validation notes | 10% |

### Important cautions

| Risk | How To Handle It |
|---|---|
| Large PRs are not always bad | Penalize only when size is not justified or reviewability is poor. |
| Small PRs are not always good | A tiny PR can still be low value, risky, or unclear. |
| Refactors can look noisy | Reward refactors when they are explained, isolated, tested, and reduce complexity. |
| AI usage cannot be proven | Do not claim someone used AI badly. Detect low-signal rewrite patterns instead. |

### Dashboard explanation

> PR Reviewability rewards engineers who submit focused, intentional diffs that are easier for teammates to review safely. It penalizes unnecessary rewrites, noisy movement, oversized unfocused PRs, and changes where reviewers had to spend extra effort understanding the author's intent.

---

## Dimension 2: Code Ownership and Post-Merge Health

### Definition

This dimension measures what happens after code is merged. It uses Git history, PR relationships, follow-up changes, reverts, and blame-like ownership signals to understand whether changes stay healthy or lead to corrective churn.

This should not be used as a blame machine. The better framing is:

> After an engineer changes important code, what happens to that area next?

### Metrics

| Metric | What It Measures | Positive Signal | Negative Signal | Possible GitHub Evidence |
|---|---|---|---|---|
| Stability after merge | Whether touched files remain stable after merge | No quick corrective follow-up | Same area gets bugfix, hotfix, revert, or regression PR soon after | PR file list, later PRs touching same files |
| Corrective churn window | Whether changes trigger near-term repairs | No corrective changes within 7, 14, or 30 days | Later PR title says fix, bug, regression, hotfix, broken, revert | PR titles, labels, changed files |
| Fix-forward impact | Who fixes fragile or broken areas | Engineer fixes bugs, regressions, security issues, flaky tests | Not applicable as penalty, this is mainly positive credit | PR labels, titles, linked issues |
| Durable simplification | Whether simplification survives after merge | Simplified code remains and later work builds on it | Removed logic is quickly restored or patched | Later diffs, same-file history |
| Fragile area stabilization | Whether engineer improves high-churn areas | Repeatedly stabilizes risky areas | Creates repeated churn in already fragile areas | File history, labels, issue links |
| Revert relationship | Whether PRs are quickly rolled back | No revert or rollback needed | Direct revert or rollback soon after merge | Revert PR title, linked PR references |
| Blame overlap confidence | Whether a later fix overlaps recently changed lines | Weak or no overlap with bugfix | Later fix touches same blamed lines or same function | Git blame, file diff, commit history |

### Suggested scoring

| Sub-score | Suggested Weight Inside Dimension |
|---|---:|
| No corrective churn after merge | 30% |
| Fix-forward impact | 25% |
| Durable simplification | 15% |
| Stabilization of fragile areas | 15% |
| Revert or rollback avoidance | 10% |
| Blame-overlap confidence | 5% |

### Confidence levels for linking original PR to later fix

| Confidence | Evidence |
|---|---|
| Low | Later PR touches one or more same files. |
| Medium | Later PR touches same file and has bugfix language within 14 or 30 days. |
| High | Later PR references the earlier PR, touches the same function, or overlaps blamed lines. |
| Very high | Later PR explicitly says it fixes a regression introduced by the earlier PR. |

### Important cautions

| Risk | How To Handle It |
|---|---|
| Same-file follow-up does not prove fault | Treat it as a health signal, not personal blame. |
| High-risk areas naturally churn more | Compare against area risk and reward stabilization work. |
| Reverts are not always bad | Sometimes revert behavior shows responsible release safety. |
| Git blame can mislead | Formatting, movement, and generated code can distort ownership. |

### Dashboard explanation

> Post-Merge Health looks at whether code remains stable after merge and who helps stabilize fragile areas. It uses follow-up fixes, reverts, bugfix chains, and ownership signals carefully, as code-health evidence rather than personal blame.

---

## Dimension 3: Requirement-Aligned Test Quality

### Definition

This dimension measures whether tests are meaningful and tied to real behavior, requirements, issues, or bug fixes. It intentionally avoids rewarding test coverage by itself.

### Main idea

> A test is valuable when it protects the requirement, not when it merely touches lines of code.

### Metrics

| Metric | What It Measures | Positive Signal | Negative Signal | Possible GitHub Evidence |
|---|---|---|---|---|
| Requirement linkage | Whether tests map to the PR goal | Test matches linked issue or feature requirement | Test exists but does not validate the requested behavior | Linked issue, PR body, test file changes |
| Regression coverage | Whether bugfixes add tests to prevent recurrence | Bugfix PR includes regression test | Bugfix has no test or only shallow test | PR title, changed test files |
| Behavior-focused assertions | Whether assertions check real outcomes | Assertions validate user-visible or domain behavior | Tests only check function calls or snapshots without intent | Test diff, test names |
| Edge-case coverage | Whether important edge cases are tested | Tests cover boundary, failure, permission, data, or migration cases | Only happy path tested | Test body, review comments |
| Test naming quality | Whether test names explain behavior | Test name describes expected behavior | Vague names like `test works` | Test code |
| Reviewer-driven test improvement | Whether review improves test quality | Reviewer asks for specific test and author adds it | Reviewer asks for tests but none added | Review comments, later commits |

### Suggested scoring

| Sub-score | Suggested Weight Inside Dimension |
|---|---:|
| Requirement linkage | 25% |
| Regression coverage | 25% |
| Behavior-focused assertions | 20% |
| Edge-case coverage | 15% |
| Test naming quality | 5% |
| Reviewer-driven test improvement | 10% |

### Important cautions

| Risk | How To Handle It |
|---|---|
| More tests are not always better | Reward test relevance, not test count. |
| Coverage can be gamed | Avoid using coverage percentage as the main signal. |
| Snapshot tests can be shallow | Reward snapshots only when they clearly protect expected behavior. |

### Dashboard explanation

> Requirement-Aligned Test Quality rewards engineers whose tests protect actual behavior, requirements, and bug fixes. It does not reward meaningless tests that only increase coverage numbers.

---

## Dimension 4: Simplicity, Readability, and Design Quality

### Definition

This dimension combines simplicity impact, code readability, and design simplicity. It measures whether an engineer makes the code easier to understand, easier to modify, and less costly to maintain.

### Metrics

| Metric | What It Measures | Positive Signal | Negative Signal | Possible GitHub Evidence |
|---|---|---|---|---|
| Safe code reduction | Whether complexity was removed safely | Less code with same or better behavior | Deleted code with no explanation or test safety | Net diff, tests, PR body |
| Duplicate logic removal | Whether repeated logic was consolidated | Repeated paths replaced by clear shared helper | Over-abstraction that makes code harder | Diff patterns, changed files |
| Dead code cleanup | Whether stale paths were removed | Removes unused flags, obsolete APIs, unreachable code | Removes active behavior accidentally | PR body, labels, files |
| Naming clarity | Whether names improve comprehension | Better names for variables, functions, modules | Cosmetic renames with no value | Diff, review comments |
| Simple control flow | Whether logic is easy to follow | Less nesting, fewer scattered conditions | More nested branches and special cases | Code diff, static analysis if available |
| Design fit | Whether change follows existing architecture | Uses established project patterns | Introduces unnecessary new patterns | File location, imports, review comments |
| Useful comments | Whether comments explain intent | Comments explain why or risk | Comments repeat obvious code | Code diff |

### Suggested scoring

| Sub-score | Suggested Weight Inside Dimension |
|---|---:|
| Safe code reduction | 20% |
| Duplicate logic removal | 20% |
| Dead code cleanup | 15% |
| Naming and readability | 15% |
| Simple control flow | 15% |
| Design fit | 10% |
| Useful comments | 5% |

### Important cautions

| Risk | How To Handle It |
|---|---|
| Simpler is not always shorter | Reward understandable design, not just fewer lines. |
| Abstractions can help or hurt | Reward abstractions only when they reduce repeated complexity. |
| Renames can be noisy | Reward renames only when they clarify meaningful code. |

### Dashboard explanation

> Simplicity and Readability reward engineers who reduce unnecessary complexity, improve structure, remove duplication, clean stale paths, and make the code easier for future engineers to understand.

---

## Dimension 5: Engineering Process Influence

### Definition

This dimension measures meaningful non-code contributions that improve the engineering process around the code. It gives credit to engineers who help shape work before, during, and after implementation.

### Metrics

| Metric | What It Measures | Positive Signal | Negative Signal | Possible GitHub Evidence |
|---|---|---|---|---|
| Substantive review comments | Whether review comments improve the code | Comments identify bugs, risks, edge cases, or better designs | LGTM-only or shallow comments | PR reviews, review comments |
| Design input | Whether engineer shapes the implementation approach | Suggests simpler or safer design that gets adopted | Vague opinion with no effect | Review thread, later commits |
| Edge-case detection | Whether engineer catches missing cases | Points out failure, permission, migration, data, or scale edge cases | No specific technical content | Review comments, issue comments |
| Test strategy influence | Whether engineer improves validation | Suggests specific tests that are added | Generic “add tests” without detail | Review comments, changed tests |
| Requirement clarification | Whether engineer reduces ambiguity | Clarifies expected behavior or constraints | Adds confusion or unresolved debate | Issue comments, PR discussion |
| Unblocking others | Whether engineer helps others move work forward | Answers technical questions, provides context, confirms direction | Comment volume with no useful action | Threads, response timing, reactions |

### Suggested scoring

| Sub-score | Suggested Weight Inside Dimension |
|---|---:|
| Substantive review comments | 30% |
| Design input | 20% |
| Edge-case detection | 20% |
| Test strategy influence | 15% |
| Requirement clarification | 10% |
| Unblocking others | 5% |

### Important cautions

| Risk | How To Handle It |
|---|---|
| Comment count can be misleading | Score usefulness, not volume. |
| Short comments can be useful | A short comment identifying a real bug should count. |
| Long comments can be low value | Length alone should not create credit. |

### Dashboard explanation

> Engineering Process Influence rewards people who improve the quality and direction of work through reviews, design suggestions, edge-case detection, testing guidance, and clarification.

---

## Dimension 6: Issue Discovery, Triage, and Resolution Impact

### Definition

This dimension measures how engineers help the team discover, understand, prioritize, route, and resolve problems using GitHub Issues.

### Metrics

| Metric | What It Measures | Positive Signal | Negative Signal | Possible GitHub Evidence |
|---|---|---|---|---|
| High-quality issue creation | Whether the issue is actionable | Clear problem, reproduction steps, expected vs actual behavior | Vague issue with no useful detail | Issue body, labels, comments |
| Bug reproduction | Whether engineer turns vague problem into fixable problem | Adds reproduction steps, logs, screenshots, environment details | No diagnostic progress | Issue comments |
| Triage quality | Whether issue is routed correctly | Correct labels, owner, priority, duplicate links | Mislabels, stale issues, unclear owner | Labels, assignees, timeline events |
| Issue-to-PR linkage | Whether problem is connected to implementation | Issue is linked to fixing PR | Issue closed without explanation | Linked PRs, closing keywords |
| Resolution efficiency | Whether important issues move forward | Quick useful response, linked PR, closure | Long delay with no meaningful action | Issue timestamps, comments, linked PR |
| Reopen or recurrence signal | Whether closure actually solved the problem | Closed issue stays closed | Issue reopened or repeated soon after | Issue events, duplicate issues |
| Cross-team coordination | Whether engineer connects relevant context | Links product, support, frontend, backend, infra context | Siloed discussion with missing context | Comments, labels, linked issues |

### Suggested scoring

| Sub-score | Suggested Weight Inside Dimension |
|---|---:|
| High-quality issue creation | 20% |
| Bug reproduction and diagnosis | 20% |
| Triage quality | 15% |
| Issue-to-PR linkage | 15% |
| Resolution efficiency | 15% |
| Reopen or recurrence handling | 10% |
| Cross-team coordination | 5% |

### Important cautions

| Risk | How To Handle It |
|---|---|
| Closing many issues does not equal impact | Reward meaningful resolution and diagnosis. |
| Issue opener is not always the resolver | Split credit across discovery, triage, diagnosis, and fix. |
| Some issues are naturally long-running | Weight by severity and complexity. |

### Dashboard explanation

> Issue Impact rewards engineers who help the team find, explain, prioritize, and resolve real problems, not just people who open or close the most issues.

---

## Dimension 7: Dependency and Duplication Hygiene

### Definition

This dimension measures whether engineers keep the codebase lean by avoiding unnecessary dependencies, removing unused packages, reducing duplicated logic, and preventing maintenance bloat.

### Metrics

| Metric | What It Measures | Positive Signal | Negative Signal | Possible GitHub Evidence |
|---|---|---|---|---|
| Dependency justification | Whether new packages are necessary | New dependency solves a real problem and is explained | Adds package for trivial or existing functionality | Package files, PR body |
| Unused dependency removal | Whether old dependencies are cleaned up | Removes unused or obsolete packages | Leaves unused dependencies in place | Package diff, lockfile diff |
| Overlapping library avoidance | Whether repo avoids multiple tools for same job | Uses existing project library | Adds duplicate library for same purpose | Imports, package files |
| Duplicate logic reduction | Whether repeated logic is reduced | Consolidates duplicated implementation | Repeats similar function in multiple places | Code diff, similar blocks |
| Security and maintenance awareness | Whether dependency risk is considered | Handles vulnerable or outdated dependencies carefully | Adds risky dependency without explanation | Dependency diff, security alerts if available |
| Lockfile discipline | Whether package changes are controlled | Lockfile changes match dependency intent | Huge lockfile churn without clear package change | Lockfile diff |

### Suggested scoring

| Sub-score | Suggested Weight Inside Dimension |
|---|---:|
| Dependency justification | 20% |
| Unused dependency removal | 20% |
| Overlapping library avoidance | 15% |
| Duplicate logic reduction | 20% |
| Security and maintenance awareness | 15% |
| Lockfile discipline | 10% |

### Important cautions

| Risk | How To Handle It |
|---|---|
| New dependencies are not always bad | Reward justified dependencies that reduce real complexity. |
| Duplication is not always bad | Sometimes a small duplicate is better than a bad abstraction. |
| Security data may be unavailable | Use it only when available and visible. |

### Dashboard explanation

> Dependency and Duplication Hygiene rewards engineers who keep the codebase lean by avoiding unnecessary packages, removing unused dependencies, reducing duplicated logic, and preventing maintenance bloat.

---

## Evidence model

Each metric should produce a small amount of explainable evidence. The dashboard should avoid showing mysterious scores without context.

### Evidence examples

| Evidence Type | Example Dashboard Text |
|---|---|
| Reviewable PR | “Submitted 8 focused PRs with low noisy-churn and clear testing notes.” |
| Diff intent | “Large PR was treated as positive because it separated migration logic and explained rollout risk.” |
| Post-merge health | “Only 1 of 9 merged PRs had likely corrective follow-up within 14 days.” |
| Fix-forward | “Fixed 3 bug/regression PRs in high-risk ingestion paths.” |
| Test quality | “Bugfix PRs usually included regression tests tied to the issue.” |
| Simplicity | “Removed stale feature flag paths while preserving tests.” |
| Process influence | “Review comments led to added edge-case tests in 4 PRs.” |
| Issue impact | “Converted vague issue reports into reproducible bugs linked to fixing PRs.” |

---

## Data sources to use

| Data Source | Useful For |
|---|---|
| Pull requests | Author, title, body, labels, merge date, changed files, additions, deletions |
| PR files | Diff size, file scope, risky areas, dependency files, test files |
| PR reviews | Reviewers, review state, review body, approval/request changes/context |
| PR review comments | Substantive feedback, edge-case detection, test suggestions, review friction |
| Issue comments | Diagnosis, triage, clarification, cross-team coordination |
| Issues | Problem discovery, labels, assignees, linked PRs, closure, reopen signals |
| Commit history | Follow-up changes, same-file churn, reverts, code ownership context |
| Git blame or blame-like data | Line ownership and stronger confidence for change-chain relationships |
| Dependency files | Package changes, lockfile churn, overlapping dependencies |
| Test files | Requirement-aligned tests, regression tests, behavior validation |

---

## Dashboard structure

The final dashboard should fit on one laptop screen.

### Header

Title:

> Engineering Impact Dashboard: Reviewable Diffs and Post-Merge Code Health

Subtitle:

> Ranking engineers by intentional PRs, post-merge stability, meaningful tests, simplicity, and engineering influence rather than raw code volume.

### Main card layout

Each top engineer card should show:

| Field | Example |
|---|---|
| Rank | #1 |
| Engineer | Name or GitHub username |
| Impact score | 86 / 100 |
| Primary strength | “Reviewable diffs + post-merge stability” |
| Evidence 1 | “Merged 10 focused PRs with low noisy-churn.” |
| Evidence 2 | “Only 1 likely corrective follow-up within 14 days.” |
| Evidence 3 | “Added regression tests for 4 bugfixes.” |
| Evidence 4 | “Review comments led to added edge-case coverage.” |
| Score breakdown | Reviewability 29, Post-Merge 21, Tests 13, Simplicity 12, Other 11 |

### Supporting table

| Engineer | Total | PR Reviewability | Post-Merge Health | Test Quality | Simplicity | Process | Issues | Dependency Hygiene |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Engineer A | 86 | 29 | 21 | 13 | 12 | 4 | 4 | 3 |
| Engineer B | 81 | 25 | 23 | 12 | 10 | 5 | 3 | 3 |
| Engineer C | 77 | 27 | 18 | 10 | 11 | 5 | 4 | 2 |

---

## Anti-patterns the dashboard should avoid

| Anti-pattern | Why It Is Bad | Better Approach |
|---|---|---|
| Ranking by commits | Commits measure activity, not impact | Use PR intent, reviewability, and outcome |
| Ranking by lines of code | More code can mean more complexity | Reward useful, stable, simple changes |
| Ranking by PR count | Many small PRs can still be low value | Score quality and evidence per PR |
| Ranking by comments | Comment count can be noise | Score substantive comments that affect code |
| Ranking by test coverage alone | Coverage can be meaningless | Score requirement-aligned tests |
| Using Git blame as personal blame | Blame is technically noisy and culturally risky | Use it as confidence for change-chain health |
| Penalizing all large PRs | Some large PRs are justified | Penalize only poor reviewability and unclear intent |
| Calling out AI usage directly | AI usage cannot be reliably proven | Detect low-signal rewrites and noisy diffs |

---

## Final recommended focus for the take-home

The dashboard should make these three dimensions the visible differentiator:

| Focus | Why It Should Be Central |
|---|---|
| PR Reviewability | Easy for evaluators to understand and validates thoughtful engineering judgment. |
| Developer Intent | Detects whether diffs are purposeful or just noisy change. |
| Post-Merge Health | Shows what happened after code landed, which most dashboards ignore. |

Supporting dimensions should improve the ranking, but should not clutter the UI. The top-five cards should explain the result in plain English.

Final positioning:

> This dashboard identifies engineers who do not just produce code, but produce changes that are reviewable, intentional, stable after merge, and helpful to the broader engineering system.
