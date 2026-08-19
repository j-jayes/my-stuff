---
name: subagent-fanout
description: >-
  Decide whether to delegate work to subagents, and write a subagent prompt that
  actually works. Use when a task spans many files or requires reading far more than
  the answer is worth, or when asked to "use subagents" or "search in parallel".
---

<!-- GENERATED from .agents/skills/subagent-fanout/SKILL.md — edit that file, then run: uv run scripts/generate_ai_docs.py -->
# Subagent fan-out

A subagent is a fresh copy of the agent with an empty context window, dispatched like any
other tool call. The parent waits for a summary instead of paying for everything the subagent
had to read.

## The one rule

**A subagent must justify itself on token economics, not on role-play.**

Context limits top out around a million tokens, and quality measurably degrades well before
that — often past ~200k. Those numbers have barely moved in two years even as the models got
much better. So the only durable reason to delegate is that the work would burn context the
parent needs for something more important.

Your main agent is perfectly capable of reviewing, debugging, or refactoring its own output,
provided it has the tokens to spare. Inventing a committee of specialists for a task that fits
comfortably in one context makes the result worse, not better: every hand-off loses detail.

## When to fan out

**Yes:**

- **Broad search.** "Where is X implemented?" across an unfamiliar repo — the subagent reads
  fifty files and returns three paths.
- **Independent edits.** The same mechanical change across files that do not depend on each
  other. Independence is the load-bearing condition; if file B's edit depends on how file A's
  turned out, run them in sequence.
- **Verbose output you only need the conclusion of.** A large test suite, a long build log.
  The subagent absorbs ten thousand lines and reports the four failures.
- **Deep external research.** Fetching and reading many pages when you need only the digest.

**No:**

- Anything you could answer by reading one or two known files. Just read them.
- Sequential work where each step needs the previous step's detail.
- Splitting a task you already understand into "roles" for their own sake.

## Writing the prompt

A subagent starts from nothing. It has none of your conversation, none of the user's phrasing,
none of what you already ruled out. The prompt has to carry all of it. The shape that works:

1. **A numbered list of the artifact categories to find** — not one vague objective.
2. **The specific directories to look in.**
3. **The literal keywords and identifiers to search for.**
4. **The breadth you want** — "search thoroughly", or "one or two files is enough".
5. **The exact shape of the answer** — file paths, a table, a yes/no with evidence.

```text
Find the code that implements the diff view for chapters in this Django blog. Find:
  1. Templates that render diffs (diff-related HTML/CSS with red/green backgrounds)
  2. Python that generates diffs (difflib or similar)
  3. JavaScript related to diff rendering
  4. CSS for the diff view

Search thoroughly — check templates/, static/, blog/. Look for the keywords
"diff", "chapter", "revision", "history", "compare".

Report file paths with line numbers and a one-line description of each. Do not
propose changes.
```

Note what it does not do: it does not say "you are a senior frontend engineer". It says what
to find, where, and in what form to answer.

## After it returns

Treat the result as a report from someone who saw things you did not. Read the files it
identified before acting on its conclusions — subagents are confidently wrong at the same rate
you are, and you cannot see their working.

---

Adapted from Simon Willison's [Agentic Engineering Patterns](https://simonwillison.net/guides/agentic-engineering-patterns/).
