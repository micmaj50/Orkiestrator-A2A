# Team workflow

This document defines how we work together in this repository

## Branches

### Main Branch

`main` should always contain the current working version of the project.

After the initial setup, we should avoid pushing directly to `main`.
Changes should normally be made in separate branches and merged through merge requests.

### Branch Naming


Use following branch prefixes:

- `feature/...` - new functionality intended for the real project. Push to origin, open a merge request, review, merge into `main`, delete branch.
- `fix/...` - bug fixes. Push to origin, open a merge request, merge into `main`, delete branch.
- `test/` - adding or improving tests without changing production behavior. Push to origin, open a merge request, review, merge into `main`, delete branch.
- `docs/...` - documentation changes. Push to origin, open a merge request, review, merge into `main`, delete branch.
- `chore/...` - tooling, configuration, dependencies, CI/CD setup. Push to origin, open a merge request, review, merge into `main`, delete branch.
- `spike/...` - short research/prototype work to answer a technical question. Push if useful for sharing or discussion. Don't merge into `main`. Useful ideas should be extracted or rewritten into a clean `feature/...` or `chore/...` branch.
- `playground/...` - personal experiments and learning code. Usually kept local. May be pushed for backup or sharing, but must never be merged into `main`.


Branches should use this format:

```text
<prefix>/<short-kebab-case-description>
```

Examples:

- `feature/agent-skill`
- `feature/basic-orchestrator`
- `fix/task-status-parsing`
- `docs/team-workflow`
- `chore/add-basic-ci`
- `spike/agent-executor`
- `playground/vlad-executor-helloworld`

## Commit naming

Commit messages should use the following format:
`<type>(<optional-scope>): <description>`

The scope is optional and identifies the component or area affected by the change.

Available commit types:

- `feat` -- new functionality intended for the real project.
- `fix` -- bug fixes.
- `test` -- test changes.
- `docs` -- documentation changes.
- `chore` -- tooling, configuration, dependencies and CI/CD changes.

Examples:

`feat(orchestrator-langgraph): add agent delegation node`
`fix(config): use configured agent endpoint`
`docs(workflow) define commit naming rules and update branch naming rules`
`chore(ci) add integration test job`

The commit type describes the individual change and does not have to match the branch prefix. For example, a feature branch may contain `feat`, `test` and `fix` commits. 
Scopes should be used when they provide useful context, such as the affected agent, component or project area. They may be omitted when the affected area is already clear or the change applies to the whole project.
Commit naming rules do not need to be enforced on `spike/` or `playground/` branches because these branches are not merged into the main branch.

## Experiments

`spike/..` and `playground/...` branches are allowed to be messy because their purpose is learning and explanation. 

However, messy experimental code should not become part of `main` directly. 

The main difference between `spike/...` and `playground/...` is: 

- `spike/...` answers a specific technical question for the team
- `playground/...` is personal learning or experimentation

## Merge requests

Use a merge request when a branch is ready to be added to the project.

Use a draft merge request when the work is unfinished but should be visible to the team.
This is useful when the branch affects interfaces, architecture or another person's work.

Before merging: 

- update the branch with the latest `main`
- check that the project still runs (when CI/CD is added)
- describe what changed
- mention anything that may affect other team members

After merging, delete the source branch.

## Tests

Tests should usually be added in the same branch as the code they verify.

Use `test/` for adding or improving tests independently, without changing production behavior.

Use `chore/` only for test infrastructure, such as `pytest`, test configuration, dependencies, or CI.

## Shared interfaces

If one's work depends on another person's work, agree on the interface early.

Examples of interfaces:

- Python Abstract Base Classes (ABC)
- expected configuration variables
- expected data formats (JSON)

If the real implementation is not ready yet, use a mock or stub so that work can continue.

## CI 

> We do not have a CI pipeline set up yet

We will add a minimal GitLab CI pipeline to run basic checks once the project is runnable. For now, please ensure your code runs locally before merging.

