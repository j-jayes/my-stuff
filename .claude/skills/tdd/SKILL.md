---
name: tdd
description: >-
  Red/green test-driven development. Write the test first, watch it fail, then make
  it pass. Use when adding a feature, fixing a bug, or whenever the user says
  "use red/green TDD", "write tests first", or reports something broken.
---

<!-- GENERATED from .agents/skills/tdd/SKILL.md — edit that file, then run: uv run scripts/generate_ai_docs.py -->
# Red/green TDD

`Red/green TDD` is shorthand for: write the tests first, **confirm they fail**, then
write the minimum code that makes them pass.

## The loop

1. **Write the test.** Express the desired behaviour as an executable assertion. For a bug,
   the test is a reproduction: it must fail *for the reason the user reported*, not for some
   incidental reason like an import error.
2. **Run it and watch it fail. Do not skip this.** This is the step people skip and it is
   the step that makes the whole thing work. A test that already passes exercises nothing —
   you will write an implementation, see green, and have proven precisely nothing. If the
   test passes before you implement anything, the test is wrong. Fix the test first.
3. **Read the failure message.** It should describe the missing behaviour. If it says
   `ModuleNotFoundError`, you are still in step 1.
4. **Write the minimum code that makes it pass.** Not the general case, not the
   configurable version — the minimum. See *Simplicity First*.
5. **Run the tests again and watch them pass.** All of them, not just the new one.
6. **Refactor now, if at all.** Green tests are the licence to refactor; without them you
   are just editing and hoping.

## What to state as you go

Show the red output and the green output. "Tests pass" without the run is a claim, not
evidence — and the whole point of this discipline is producing evidence.

## Where bugs come from

Anything found by hand comes back through this loop. A bug you found by poking at the app,
fixed directly, and moved on from will return. A bug you found by poking at the app, wrote a
failing test for, then fixed, is gone permanently and the suite is one test stronger.

That is the payoff cycle:

```text
manual testing finds a bug
        -> write a failing test that reproduces it   (red)
        -> fix it                                    (green)
        -> the regression suite is permanently better
```

## When not to bother

Throwaway exploration in a scratch directory, and one-line changes to comments or docs.
Everything that ships gets a test.

---

Adapted from Simon Willison's [Agentic Engineering Patterns](https://simonwillison.net/guides/agentic-engineering-patterns/).
