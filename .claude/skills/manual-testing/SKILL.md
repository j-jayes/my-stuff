---
name: manual-testing
description: >-
  Drive the real thing and prove it works — interpreter one-liners, curl against a
  dev server, a browser, a screenshot. Use before claiming any change works, when
  asked to "test it by hand", "check it actually works", or "show me it working".
---

<!-- GENERATED from .agents/skills/manual-testing/SKILL.md — edit that file, then run: uv run scripts/generate_ai_docs.py -->
# Agentic manual testing

**Never assume that code you generated works until that code has been executed.**

Passing unit tests are not the same as working software. Tests routinely pass on code that
crashes on startup, renders a blank page, or drops the one field the user cared about. Before
you say a change works, run the real thing and look at the result.

## Pick the cheapest mechanism that exercises the real path

| Situation | Do this |
| --- | --- |
| A Python function | `python -c` with a multi-line string — import the module and try edge cases, including the empty, null and oversized ones |
| A dataframe transform | Load a small real slice, run the transform, print `.shape`, `.head()`, and the null counts before and after |
| A compiled language | Write a scratch main in a temp directory, compile it, run it. Temp directory so it cannot be committed by accident |
| An HTTP API | Start the dev server, then `curl` it. Say "explore the API" and try several endpoints and error cases, not just the happy path |
| A web page | Serve it (`python -m http.server` — pages that fetch data break when opened as `file://`) and drive a browser |
| A CLI | Run `--help`, then run it for real on a fixture |

## Browser work

Tell the agent runtime which tool to use and give it something concrete to test against:

- **Playwright** is the general answer; it drives every major engine and has bindings everywhere.
- Ask for **screenshots** explicitly. That is the cue to actually look at the rendered page
  with vision rather than reasoning about the DOM in the abstract.
- For any CLI you have not used before, run `<tool> --help` first. Good agent-facing CLIs put
  everything you need in their help output, and `uvx <tool> --help` installs it in the same step.

Browser tests used to be avoided as flaky and expensive to maintain. That calculus changed:
keeping them current is now cheap.

## Always give yourself something to check against

The single biggest determinant of whether this works is whether you have a **validation
mechanism**: a fixture file, a URL that is known to render correctly, an existing feature that
already behaves the way the new one should, a previous output to diff against. Find one before
you start. "Compare what the new export produces against what the existing page shows" is worth
more than a paragraph of specification.

## Close the loop

Anything you break while poking at it gets fixed through red/green TDD, so it becomes a
permanent test rather than a thing you happened to notice once. See the `tdd` skill.

## Report what you did

Record the commands you ran and their real output — not a summary of what you expected. If a
change is visual, include a screenshot. This is also what a reviewer needs from you: evidence
that their time will not be wasted.

---

Adapted from Simon Willison's [Agentic Engineering Patterns](https://simonwillison.net/guides/agentic-engineering-patterns/).
