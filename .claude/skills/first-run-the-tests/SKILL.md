---
name: first-run-the-tests
description: >-
  Orient yourself in a repository before changing anything: run the test suite,
  then read recent git history. Use at the start of a session in an unfamiliar
  project, or when asked to "get up to speed", "first run the tests", or
  "review recent changes".
---

<!-- GENERATED from .agents/skills/first-run-the-tests/SKILL.md — edit that file, then run: uv run scripts/generate_ai_docs.py -->
# First run the tests

Two commands, run before you write anything, buy you most of what you need to know
about a codebase. Do both.

## 1. Run the suite

Find and run the tests. For a Python project that is usually `uv run pytest`; check
`pyproject.toml`, `Makefile`, or `package.json` for the project's actual command and
prefer that over guessing.

This is not busywork. It does three things at once:

1. **It proves a suite exists and teaches you how to run it**, which makes it far more
   likely you will run it again after you change something.
2. **The test count is a proxy for the size and shape of the project.** Nine tests and
   nine hundred are different codebases.
3. **It puts you in a testing mindset**, so extending the suite feels like the default
   rather than an extra chore.

If the suite fails before you have touched anything, say so and stop. You need to know
whether you inherited a broken tree or broke it yourself, and a red baseline makes every
later signal worthless.

If there is no suite at all, say that too — it is the single most important fact about
the repository, and it changes how you should work in it.

## 2. Read the recent history

```bash
git log --oneline -20
git log -p -3
```

Reading recent commits loads your context with what the humans have actually been doing:
the modified code *and* the commit messages describing why. That is usually a better
starting point than any summary of the repository, and it lets the conversation start
from "what came before" rather than from nothing.

Widen it when the change you are about to make touches something older:

```bash
git log --oneline -- path/to/file       # history of one file
git log -S "some_function" --oneline    # every commit that added or removed the string
```

## Then report

Before proposing a change, state in a sentence or two: how the tests are run, whether they
pass, roughly how many there are, and what the last few commits were doing. Then start work.

---

Adapted from Simon Willison's [Agentic Engineering Patterns](https://simonwillison.net/guides/agentic-engineering-patterns/).
