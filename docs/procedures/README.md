# Procedures

One document per recurring job that spans several files and fails silently.
`docs/components/` says how the tree **is**; a procedure says how a **job** in
it is done, in the order it has to be done. Adding one:
[`../conventions/procedures.md`](../conventions/procedures.md).

| Procedure | Read it when |
|---|---|
| [`pad-bindings.md`](pad-bindings.md) | Binding a button, writing an application profile, lending the keyboard a page, or asking "which button should this be?". |
| [`pad-surface.md`](pad-surface.md) | Adding or changing a surface - a daemon model, its socket, its QML panel. Also when a panel will not draw or ignores half its data. |
| [`pad-setting.md`](pad-setting.md) | Turning a number into a setting, or adding one. |
| [`pad-menu.md`](pad-menu.md) | Adding or reordering `[[menu.items]]` rows. |
| [`pad-wording.md`](pad-wording.md) | Writing or fixing anything a user reads - a menu `label`/`detail`, a binding's `desc`/`short`, CLI output. |
| [`pad-badge-art.md`](pad-badge-art.md) | Touching `assets/shapes/`, supporting a pad that prints something new, or a badge that shows typed text. |
| [`pad-diagnose.md`](pad-diagnose.md) | Anything that works in the tests but not on the machine. |

The blockquote under each title is that document's trigger, kept as one
paragraph on purpose: it is the part read when deciding whether this job is the
job at hand.

## Why these are not agent skills

They were `.claude/skills/pad-*/SKILL.md` until 1.3.1. That folder is a file
format a coding agent loads **by itself**, and this repository is installed as
an Omarchy plugin: `omarchy plugin add` and `boot.sh` both clone the whole
checkout into `~/.config/omarchy/plugins/canerakdas.omapad`, on a machine whose
owner asked for an on-screen keyboard and not for a set of instructions
addressed to their tools. Whatever this project ships to a user is a payload,
and instructions that something executes without being asked do not belong in
one. Nothing under `docs/` is loaded by anything; it is read by a person, or
handed to an agent by a person, which is the difference.

This is a rule about the tree, not about the tooling. See
[`../conventions/procedures.md`](../conventions/procedures.md) for wiring these
into an agent on your own machine, which stays out of the repository.
