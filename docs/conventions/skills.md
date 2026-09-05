# Skills

`.claude/skills/` holds one folder per recurring job. A skill is not more
documentation: `docs/` says how the tree **is**, a skill says how a **job** in
it is done, in the order it has to be done. So the two never restate each
other - where a rule is already in `docs/`, the skill links it and applies it.

Rules here are normative in the same way the language guides are; see
[`README.md`](README.md) for how MUST / SHOULD / MAY are meant.

## When a job earns a skill

All three tests, or it is not a skill:

| Test | It fails when |
|---|---|
| **It recurs.** | it happened once. A one-off belongs in the commit message. |
| **It spans files.** | it lives in one file - then it is that file's docstring, or that component's doc. |
| **It fails silently.** | the mistake raises. A traceback that names the line is already the skill; `omapad check` was written so that most config mistakes are that kind. |

The job SHOULD also have an end a command can prove - `omapad check`, a test
module, a guide page read back as words. A skill with nothing to verify tends
to be an opinion, and opinions go in `docs/conventions/`.

Where the knowledge goes when a job fails a test:

| The knowledge is about | It goes in |
|---|---|
| One function or module | its docstring |
| One component's contract | `docs/components/<name>.md` |
| How to write in a language | `docs/conventions/<language>.md` |
| A job crossing several of those, silently | `.claude/skills/pad-<job>/SKILL.md` |

## Naming

| Rule | | Why |
|---|---|---|
| The folder is `.claude/skills/<name>/`, the file inside it is always `SKILL.md` | MUST | The loader demands the name; it is not ours to choose. See [`naming.md`](naming.md). |
| `<name>` is `kebab-case` and starts with `pad-` | MUST | Skill names are flat within a session: this project's sit in one list beside the machine's own (`omarchy`, `diagnose-crash`) and any other plugin's. A skill called `menu` or `setting` claims a word it cannot own. |
| `<name>` after the prefix names the **job**, in the words someone asking for it would use - not the component that implements it | MUST | `pad-badge-art`, not `pad-assets`; `pad-wording`, not `pad-writing-conventions`. Nobody asks for a component. |
| One or two words after the prefix | SHOULD | Seven of seven are; a third word is usually two jobs. |
| `name:` in the frontmatter is the folder name, exactly | MUST | They are matched by hand, and a mismatch is silent. |
| A supporting file beside `SKILL.md` is `kebab-case.md` | MAY | None exist yet. Add one only when `SKILL.md` would go past its length; see below. |

## The description is the trigger, not a summary

The `description:` is the only part read when deciding whether this job is the
job at hand, so it is written for that decision and nothing else. Three
sentences, in this order:

| | The sentence | Example |
|---|---|---|
| 1 | What the skill does, then ` - `, then the concrete things it touches. Names `omapad` or a path only this project has. | `Add or change an omapad surface - a daemon-side model plus the QML panel that draws it and the socket between them.` |
| 2 | `Use when ...`: the triggers, **including the phrasings a person actually types, quoted**. | `Use when asked to "add a new screen/overlay/panel", "make the daemon show X", or when a panel is not drawing.` |
| 3 | What it owns or enforces. | `Covers the wiring checklist and the three silent failure modes.` |

- The first sentence MUST carry the project name or a project-only path. A
  description that could belong to any repository will be matched against any
  repository's question.
- Sentence 2 MUST include at least one failure symptom ("when a panel is not
  drawing", "when `tests/test_assets.py` fails") as well as the requests.
  Half the times a skill is needed, nobody knows to ask for it.
- Sentence 3 SHOULD be there (six of seven have it; `pad-setting` is the one
  that does not) and is what keeps two skills from claiming the same row:
  `pad-wording` **owns** the two voices, so `pad-menu` says `covers row
  kinds` and defers.
- NEVER describe the file instead of the job ("This skill contains steps
  for ..."). The reader is choosing a job, not a document.

## The body

The shape all seven share:

1. `# <Job>` as an activity, not a component: *Binding an application to the
   pad*, *Diagnosing a live pad*, *Words on the screen*.
2. Two to four lines saying **what makes the job hard**, usually the silent
   failure and the constraint behind it. No summary of the sections below.
3. The link to whatever is normative, on its own line, said as an order:
   *Read `docs/conventions/qml.md` before ...*. Six of seven link at least one
   `docs/` file, with the `../../../docs/...` path.
4. The procedure. Numbered `###` steps when order is load-bearing (a wrong
   order is the failure), plain `##` sections when it is not.
5. The commands that prove it worked: `## Verifying`. Five of seven carry
   one and three end on it; the two without are commands throughout.

And the rules the seven keep:

- **A skill applies rules; it does not own them.** A rule copied out of
  `docs/` is a second copy to keep true. Quote the one line that decides, link
  the rest.
- **Tables over prose** for anything with cases - six of seven lean on them,
  `pad-bindings` for twenty-seven rows. A paragraph is for the reason a
  table cannot hold.
- **Every command and path is real and pasteable.** The skill is read while
  doing the job, not before it.
- **Say what a choice costs**, not only what to do. `pad-bindings` spends
  buttons, `pad-menu` spends rows on a screen; a skill that only lists options
  hands back the decision it exists to make.

## Length, wrapping, spelling

- Prose wraps at **79 columns**, like the rest of the tree. A table row and
  the frontmatter `description:` stay on one line however long they run, as
  they do everywhere else in `docs/`.
- A `SKILL.md` runs **99 to 254 lines** today. Past ~250 it has stopped being
  a procedure: split the reference half into a `kebab-case.md` beside it, and
  leave the steps in `SKILL.md`.
- British spelling in prose, and American only where an API name demands it,
  as everywhere else in `docs/`. A spaced hyphen, never an em dash: there are
  none in the seven, and a skill is read in a terminal.

## The voice

A skill is written in the **argument** voice: it says why the constraint
exists, because whoever reads it is about to make a decision. That is the
opposite of the strings it teaches you to write, which are the **interface**
voice - about forty characters, no metaphor, no *your*. Both live in the same
file and must not swap places; the rules are
[`writing.md`](writing.md), and every example string inside a skill obeys them.

## Adding a skill

1. `.claude/skills/pad-<job>/SKILL.md`, frontmatter first, three sentences.
2. Link what is normative instead of restating it.
3. End with the commands that prove the job is done.
4. Add it to the enumeration in [`../README.md`](../README.md) and to the
   skills table in the workspace `CLAUDE.md`, which is where a session first
   sees that it exists.

## The seven as they stand

| Skill | Lines | Description, in characters | Ends with |
|---|---|---|---|
| `pad-badge-art` | 134 | 384 | a symptom (`When a badge shows typed text`) |
| `pad-bindings` | 254 | 370 | the action grammar, after `### 5. Verify` |
| `pad-diagnose` | 169 | 340 | `## What not to do` |
| `pad-menu` | 148 | 362 | `## Verifying` |
| `pad-setting` | 141 | 371 | an audit section, after `## Verifying` |
| `pad-surface` | 155 | 392 | `## Verifying` |
| `pad-wording` | 99 | 390 | `## Verifying` |

Descriptions run 340 to 392 characters, and that is the budget: everything
above fits in it, and a fourth sentence does not.

One of the seven disagreed with this guide when it was written.
`pad-badge-art` opened *Change the drawn controller buttons omapad badges
with -*, which named neither a job nor the files, and it had no third
sentence; it was rewritten in the change that added this file. The rest were
measured as they stood.
