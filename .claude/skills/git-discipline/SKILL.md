---
name: git-discipline
description: >-
  Use git as an investigative tool and author its history deliberately — recover lost
  work, bisect a regression, split and reword commits, prepare a reviewable PR. Use
  when asked about recent changes, when a bug "used to work", when git is in a mess,
  or before opening a pull request.
---

<!-- GENERATED from .agents/skills/git-discipline/SKILL.md — edit that file, then run: uv run scripts/generate_ai_docs.py -->
# Git discipline

A clone contains the full history, so digging through it costs nothing — no network, no
waiting. That makes several genuinely powerful git features worth reaching for routinely
instead of once a year.

## History as an investigative tool

| Question | Command |
| --- | --- |
| What has been happening here? | `git log --oneline -20`, then `git log -p -3` |
| When did this line appear, and why? | `git log -S "<string>" --oneline`, then `git show <sha>` |
| Who changed this and in what commit? | `git blame -L 40,60 path/to/file` |
| When did this break? | `git bisect` — see below |
| Where did my uncommitted work go? | `git reflog`, then `git stash list`, then search other branches |
| How do these branches differ? | `git log --oneline main..HEAD`, `git diff main...HEAD` |

**Bisect deserves special mention.** It is the most powerful debugging tool in git and almost
nobody uses it, because expressing the bug as a script that git can run automatically is
tedious. Writing that script is exactly the kind of boilerplate an agent should absorb. When
someone says "this used to work", write the reproduction as a command that exits non-zero on
failure, then:

```bash
git bisect start <bad-sha> <good-sha>
git bisect run <your-reproduction-command>
```

That turns a vague regression report into a specific commit.

**Nothing is lost until it is garbage collected.** Before telling anyone work is gone, check
`git reflog`, `git stash list`, `git fsck --lost-found`, and every other branch.

## History is authored, not recorded

The git history is not a transcript of what happened. It is a **deliberately authored story
about how the software got here**, written for whoever has to understand it next. That means
editorial decisions are legitimate: squash the six commits of flailing, split the one commit
that does three unrelated things, reword the message that says "fix".

Routine operations worth doing without being asked twice:

```bash
git commit --amend                       # fix the last message or add a forgotten file
git rebase --onto ...                    # move a branch to a better base
git reset --soft HEAD~3                  # collapse three commits, then recommit properly
```

Every one of these is reversible via the reflog, so the risk of trying is low. Confirm before
rewriting history that has already been pushed to a shared branch.

## Before you open a pull request

**Do not file a PR containing code you have not read yourself.** If you push hundreds of
generated lines you have not reviewed, you have not done the work — you have moved it onto the
reviewer, who could have prompted an agent themselves.

A good PR:

1. **Works, and you know it works** — because you ran it, not because it looked right.
2. **Is small enough to review efficiently.** Several small PRs beat one big one, and splitting
   commits is cheap when an agent does the git work.
3. **Explains the higher-level goal**, and links the issue or spec it serves.
4. **Has a description you have actually read.** Generated PR descriptions are fluent and
   sometimes wrong; it is rude to ask someone to read text you have not checked.

Include evidence that you did the first pass: the commands you ran, the output, a screenshot
if it is visual. See the `manual-testing` skill.

## Commit messages

Say *why*, not *what* — the diff already says what. Frontier models have good taste here; the
constraint is honesty about intent, not prose quality.

---

Adapted from Simon Willison's [Agentic Engineering Patterns](https://simonwillison.net/guides/agentic-engineering-patterns/).
