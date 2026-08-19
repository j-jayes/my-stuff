---
name: walkthrough
description: >-
  Produce a linear, top-to-bottom explanation of how a piece of code actually works,
  with code snippets read from disk rather than retyped. Use when asked to "explain
  this code", "give me a walkthrough", "how does this work", or when onboarding onto
  an unfamiliar module.
---

<!-- GENERATED from .agents/skills/walkthrough/SKILL.md — edit that file, then run: uv run scripts/generate_ai_docs.py -->
# Linear walkthrough

When you lose track of how code works — code you inherited, code you forgot, or code an agent
wrote for you — you take on **cognitive debt**. It behaves like technical debt: once the core
of a system is a black box, you can no longer reason confidently about it, and planning the
next change gets slower and slower.

The remedy is to explain it, in order, out loud, with the real code in front of you.

## Steps

1. **Read the source first.** All of it in scope. Do not start writing while still discovering.
2. **Plan the order.** A walkthrough is linear: entry point, then the path a real request or a
   real row of data takes through the system. Not file-by-file, and not alphabetical.
3. **Write it to a file** — `docs/walkthroughs/<topic>.md` or `notes/<topic>.md`. A walkthrough
   that only exists in a chat transcript is gone tomorrow.
4. **Never retype code into the document.** Emit each snippet by *running a command that reads
   the file*:

   ```bash
   sed -n '40,72p' src/pipeline/features.py
   ```

   Copying by hand invites silent hallucination — a plausible line that is not the line on disk.
   Running the command makes that impossible.
5. **Explain each snippet after showing it**: what it does, why it exists, what would break
   without it, and what surprised you.
6. **One diagram, if the shape is not obvious from the order.** A Mermaid `flowchart` or
   `sequenceDiagram` for how the components connect. One diagram, not one per section.

## Escalating when it still isn't clear

A walkthrough tells you the structure. Sometimes structure is not the problem — the *mechanism*
is. If after the walkthrough you still could not reimplement the tricky part from memory, build
an **interactive explanation**: a single self-contained HTML page that animates the algorithm
step by step, with a slider that can be paused, sped up, and stepped frame by frame.

The escalation ladder:

```text
summary  ->  still opaque  ->  linear walkthrough  ->  mechanism still not intuitive  ->  animation
```

"Archimedean spiral placement with per-word random angular offset" is a description. Watching
each word try a spot, collide, and spiral outward is understanding.

## Keeping it honest

- Every claim about behaviour should be traceable to a snippet you displayed.
- If you do not know why something is the way it is, say so in the document. Guessing in a
  document that will be trusted later is worse than an open question.
- Run the code where you can, and paste the actual output.

---

Adapted from Simon Willison's [Agentic Engineering Patterns](https://simonwillison.net/guides/agentic-engineering-patterns/).
