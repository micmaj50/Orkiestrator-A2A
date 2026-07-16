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

Tests should usually be added in the same branch as the code they test.

For example, if a branch adds an agent-skill, the same branch should also add or update tests for that.

Use `chore/...` only for test infrastructure, such as adding `pytest`, test configuration, or CI.

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

