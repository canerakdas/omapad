# Procedures

[`../procedures/`](../procedures/) holds one document per recurring job. A
procedure is not more documentation: `docs/components/` says how the tree
**is**, a procedure says how a **job** in it is done, in the order it has to be
done. So the two never restate each other - where a rule is already in `docs/`,
the procedure links it and applies it.

Rules here are normative in the same way the language guides are; see
[`README.md`](README.md) for how MUST / SHOULD / MAY are meant.

## Nothing in this repository is addressed to an agent

| Rule | | Why |
|---|---|---|
| No tracked file may be one a coding agent loads on its own - `.claude/`, `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, `.cursorrules` and whatever the next tool invents | MUST | This checkout **is** the plugin: `omarchy plugin add` clones it into `~/.config/omarchy/plugins/`, and `boot.sh` clones it there too. A file that a tool reads without being asked is then instructions arriving on a stranger's machine inside a payload they installed to get an on-screen keyboard. A prose document under `docs/` reaches an agent only when its owner hands it over, and that is the whole difference. |
| A procedure is `docs/procedures/pad-<job>.md` | MUST | `kebab-case.md` under `docs/`, like every other document here. See [`naming.md`](naming.md). |
| Wiring a procedure into your own agent stays untracked | MUST | `.gitignore` covers `.claude/`, so a local skill folder pointing at these files never becomes something other people install. Keep the pointer, not a copy: two copies of a procedure drift, and the tracked one is the one under review. |

The `pad-` prefix predates the move and stays. It was there because skill names
are flat within a session; it survives because seven documents named
`bindings.md`, `menu.md` and `setting.md` would sit one folder away from
`conventions/bindings.md` and `components/menu.md` and mean something else.

## When a job earns a procedure

All three tests, or it is not a procedure:

| Test | It fails when |
|---|---|
| **It recurs.** | it happened once. A one-off belongs in the commit message. |
| **It spans files.** | it lives in one file - then it is that file's docstring, or that component's doc. |
| **It fails silently.** | the mistake raises. A traceback that names the line is already the procedure; `omapad check` was written so that most config mistakes are that kind. |

The job SHOULD also have an end a command can prove - `omapad check`, a test
module, a guide page read back as words. A procedure with nothing to verify
tends to be an opinion, and opinions go in `docs/conventions/`.

Where the knowledge goes when a job fails a test:

| The knowledge is about | It goes in |
|---|---|
| One function or module | its docstring |
| One component's contract | `docs/components/<name>.md` |
| How to write in a language | `docs/conventions/<language>.md` |
| A job crossing several of those, silently | `docs/procedures/pad-<job>.md` |

## Naming

| Rule | | Why |
|---|---|---|
| `pad-<job>.md`, `kebab-case` | MUST | One file, named like every other document in `docs/`. |
| `<job>` names the **job**, in the words someone asking for it would use - not the component that implements it | MUST | `pad-badge-art`, not `pad-assets`; `pad-wording`, not `pad-writing-conventions`. Nobody asks for a component. |
| One or two words after the prefix | SHOULD | Seven of seven are; a third word is usually two jobs. |
| A supporting file beside it is `kebab-case.md` | MAY | None exist yet. Add one only when the procedure would go past its length; see below. |

## The trigger is not a summary

Every procedure opens with its title and then a blockquote, and that
blockquote is the only part read when deciding whether this job is the job at
hand. It is written for that decision and nothing else. Three sentences, in
this order:

| | The sentence | Example |
|---|---|---|
| 1 | What the procedure does, then ` - `, then the concrete things it touches. Names `omapad` or a path only this project has. | `Add or change an omapad surface - a daemon-side model plus the QML panel that draws it and the socket between them.` |
| 2 | `Use when ...`: the triggers, **including the phrasings a person actually types, quoted**. | `Use when asked to "add a new screen/overlay/panel", "make the daemon show X", or when a panel is not drawing.` |
| 3 | What it owns or enforces. | `Covers the wiring checklist and the three silent failure modes.` |

- The first sentence MUST carry the project name or a project-only path. A
  trigger that could belong to any repository will be matched against any
  repository's question.
- Sentence 2 MUST include at least one failure symptom ("when a panel is not
  drawing", "when `tests/test_assets.py` fails") as well as the requests.
  Half the times a procedure is needed, nobody knows to ask for it.
- Sentence 3 SHOULD be there (six of seven have it; `pad-setting` is the one
  that does not) and is what keeps two procedures from claiming the same row:
  `pad-wording` **owns** the two voices, so `pad-menu` says `covers row
  kinds` and defers.
- NEVER describe the file instead of the job ("This document contains steps
  for ..."). The reader is choosing a job, not a document.

## The body

The shape all seven share:

1. `# <Job>` as an activity, not a component: *Binding an application to the
   pad*, *Diagnosing a live pad*, *Words on the screen*.
2. The trigger blockquote, then two to four lines saying **what makes the job
   hard**, usually the silent failure and the constraint behind it. No summary
   of the sections below.
3. The link to whatever is normative, on its own line, said as an order:
   *Read `docs/conventions/qml.md` before ...*. Six of seven link at least one
   `docs/` file, with the `../conventions/...` path.
4. The procedure. Numbered `###` steps when order is load-bearing (a wrong
   order is the failure), plain `##` sections when it is not.
5. The commands that prove it worked: `## Verifying`. Five of seven carry
   one and three end on it; the two without are commands throughout.

And the rules the seven keep:

- **A procedure applies rules; it does not own them.** A rule copied out of
  `docs/` is a second copy to keep true. Quote the one line that decides, link
  the rest.
- **Tables over prose** for anything with cases - six of seven lean on them,
  `pad-bindings` for twenty-seven rows. A paragraph is for the reason a
  table cannot hold.
- **Every command and path is real and pasteable.** The procedure is read while
  doing the job, not before it.
- **Say what a choice costs**, not only what to do. `pad-bindings` spends
  buttons, `pad-menu` spends rows on a screen; a procedure that only lists
  options hands back the decision it exists to make.

## Length, wrapping, spelling

- Prose wraps at **79 columns**, like the rest of the tree, and the trigger
  blockquote wraps with it. A table row stays on one line however long it
  runs, as it does everywhere else in `docs/`.
- A procedure runs **102 to 256 lines** today. Past ~250 it has stopped being
  a procedure: split the reference half into a `kebab-case.md` beside it, and
  leave the steps in the procedure.
- British spelling in prose, and American only where an API name demands it,
  as everywhere else in `docs/`. A spaced hyphen, never an em dash: there are
  none in the seven, and a procedure is read in a terminal.

## The voice

A procedure is written in the **argument** voice: it says why the constraint
exists, because whoever reads it is about to make a decision. That is the
opposite of the strings it teaches you to write, which are the **interface**
voice - about forty characters, no metaphor, no *your*. Both live in the same
file and must not swap places; the rules are
[`writing.md`](writing.md), and every example string inside a procedure obeys
them.

## Adding a procedure

1. `docs/procedures/pad-<job>.md`, title first, then the trigger blockquote.
2. Link what is normative instead of restating it.
3. End with the commands that prove the job is done.
4. Add it to the table in [`../procedures/README.md`](../procedures/README.md)
   and to the one in the workspace `CLAUDE.md`, which is where a session first
   sees that it exists.

## Wiring them into an agent, on your own machine

The repository ships prose. If you want a coding agent to reach for these on
its own, that belongs in your own configuration, not in the tree - and a
pointer, never a copy, so there is one text to keep true:

```bash
# untracked: .gitignore covers .claude/
mkdir -p .claude/skills/pad-wording
cat > .claude/skills/pad-wording/SKILL.md <<'EOF'
---
name: pad-wording
description: <the trigger blockquote, joined back into one line>
---
Read docs/procedures/pad-wording.md in this repository and follow it.
EOF
```

`~/.claude/skills/` works the same way and follows you between checkouts.

## The seven as they stand

| Procedure | Lines | Trigger, in characters | Ends with |
|---|---|---|---|
| `pad-badge-art` | 137 | 384 | a symptom (`When a badge shows typed text`) |
| `pad-bindings` | 256 | 370 | the action grammar, after `### 5. Verify` |
| `pad-diagnose` | 171 | 340 | `## What not to do` |
| `pad-menu` | 150 | 362 | `## Verifying` |
| `pad-setting` | 143 | 371 | an audit section, after `## Verifying` |
| `pad-surface` | 158 | 392 | `## Verifying` |
| `pad-wording` | 102 | 390 | `## Verifying` |

Triggers run 340 to 392 characters, and that is the budget: everything above
fits in it, and a fourth sentence does not.

One of the seven disagreed with this guide when it was written.
`pad-badge-art` opened *Change the drawn controller buttons omapad badges
with -*, which named neither a job nor the files, and it had no third
sentence; it was rewritten in the change that added this file. The rest were
measured as they stood.
