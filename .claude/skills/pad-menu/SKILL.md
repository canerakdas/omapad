---
name: pad-menu
description: Add, reorder or review rows in the omapad controller menu - the [[menu.items]] tree the pad walks with the D-pad. Use when asked to "add X to the menu", "put a launcher/setting/toggle on the pad", "reorganise the menu", or when a menu row does nothing, does not tick, or throws you out of a submenu. Covers row kinds, launch-or-focus, and what belongs on a sofa.
---

# Menu rows

The controller menu is the one door that reaches past an app holding the pad,
so it is where a capability goes when it cannot have a button. It is a list,
not a radial: a radial reads a stick angle in one flick but caps out at a
handful of entries and has nowhere to put a submenu.

Read [`docs/components/menu.md`](../../../docs/components/menu.md) first. Rows
use **the same action grammar as a button binding**, so the menu reaches
anything a button can - see
[`../../../docs/conventions/bindings.md`](../../../docs/conventions/bindings.md).

**What the row says is a second job**, with a standard of its own:
[`../../../docs/conventions/writing.md`](../../../docs/conventions/writing.md),
and the `pad-wording` skill. A row that does the right thing and reads as a
riddle from the sofa is not finished.

## The one question to ask first

**Does this belong on a sofa?** The menu is walked with a thumb from across a
room, not browsed. Two things disqualify a row:

- **It says nothing when it cannot work.** A launcher for something that is
  not installed is worse from a sofa than no row at all - you press it and the
  screen does not change. Battle.net is kept out of the shipped menu for
  exactly this. Either ask first (`omarchy-cmd-present`) or leave it out.
- **It wants a keyboard.** The real Omarchy menu is a hold on PLUS precisely
  because it is driven by typing. Do not reimplement it here.

## Row kinds

An entry needs a `label`, and has **either** an `action` **or** nested `items`
- never both. `build()` parses actions at load, so a typo surfaces in
`omapad check` rather than doing nothing at the press.

```toml
[[menu.items]]
icon = "󰀻"                      # any glyph in the shell's font
label = "All apps"
detail = "Everything installed"   # the second line; optional
action = "exec:omarchy-menu toggle apps"
```

| Field | What it does |
|---|---|
| `label` | required |
| `icon` | a glyph the shell's font has |
| `detail` | one line under the label - written once, so it cannot know anything live. ~40 characters, says what happens: `pad-wording` |
| `action` | the binding grammar, parsed at load |
| `items` | a submenu; mutually exclusive with `action` |
| `repeat` | a row you **nudge** rather than pick: hold A and it repeats, the menu stays put. Volume, brightness, a speed |
| `stay` | one press, menu stays up. What a row that changes a setting the menu itself prints needs |
| `from` | a command whose output **is** the submenu, read at the press. With `action` as the template each line runs, and `empty` for what the page says when it finds nothing |
| `when` | the states the row is offered in - `game`, `handed_over`, `locked`, any one of them being enough. Read when the menu opens. For a row that could do nothing useful elsewhere: the workspace lock has nothing to lock to on a desktop |

`repeat` implies `stay`. Both are rejected on a submenu row - `MenuError` says
which path.

**The default is that the menu closes first and the command runs after**, so
the window you opened is not left behind the dimming. `stay` is the exception,
and it is what a setting row wants: choosing a badge layout and being thrown
out means opening the menu four times to try two of them.

## Rows that know the answer

A row that *sets* something is **ticked** while that thing is in force, which
is the whole difference between a list of choices and a list of guesses. The
daemon answers that, not the row: `view_state(opened, state, value)` takes
`state(action)` for the tick and `value(action)` for a row that steps a number.

A number cannot be ticked - every step is equally "not the case" - so those
rows print where they have got to instead (`9 notches a second`), and `value`
replaces the row's own `detail`. If a setting you add should tick or print,
it needs to be in `CHOSEN`; see the `pad-setting` skill.

## Rows you cannot write down

Which speakers are in the room is not something a config file knows: plug a
television in and there is one more. A row that could only name what was
written down would be pointing at whatever was there the day it was written, so
that row **lists** instead:

```toml
[[menu.items.items]]
label = "Output"
detail = "Speakers, headphones, the TV"
empty = "No outputs found"                            # if it prints nothing
action = "exec:omarchy-audio-output-set-default %1 %2"
from = "..."     # prints: label \t %1 \t %2, one row per line
```

- The command runs **every time the row is entered** - that is the point of it.
  It runs on the event loop, so `[menu] list_timeout_ms` is the pause a press
  may take; keep the command to one that answers quickly.
- A label that starts with `*` is **ticked** - the mark `pactl` and `wpctl`
  already print beside the current device. Without it the page is a list of
  guesses.
- Values are quoted as they go in, so a device that names itself from its own
  USB descriptor cannot become a second command. Write the command so each
  value is one argument.
- Picking a listed row keeps the menu up and moves the tick, so two of them can
  be tried without reopening anything.
- `empty` is a user-facing line like any other: `pad-wording`, not a stack
  trace.

## Launching something

```toml
# Launch **or focus**: with a pointer this slow, a second copy of a chat client
# is never what was asked for.
action = "exec:omarchy-launch-or-focus discord \"...\""
```

- `omarchy-launch-or-focus <class> <command>` matches the class **and** the
  title, so it finds the window whichever way the thing was installed.
- `omarchy-cmd-present <cmd> && ... || ...` is how a row copes with an app
  that may be a native client **or** an Omarchy webapp - the two have nothing
  in common but the name.
- Omarchy has its own launcher for some apps (`omarchy-launch-spotify`) that
  focuses a running one and offers to install a missing one. Prefer it.
- `exec:` runs in a transient scope of its own, so a daemon restart does not
  kill what you opened.

## Ordering

The shipped order is the argument: **what a couch reaches for first**. Steam
leads because on a sofa that is what the menu is opened for; the apps that
make a sofa a sofa follow; "All apps" is last because it is a list no
controller menu should try to be.

When adding a row, place it by frequency from the couch, not by category.

## Verifying

```bash
./bin/omapad check              # parses every row; names the path of a bad one
systemctl --user restart omapad
./bin/omapad ctl menu toggle    # walk it without the pad
```

Then walk it with the D-pad and check three things: the row does something
visible, a setting row is ticked when it is in force, and getting back out is
one press of B per level.
