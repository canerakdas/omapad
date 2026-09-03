---
name: pad-wording
description: Write or fix any text a user reads on omapad - a menu row's label and detail, a binding's desc or short, a keyboard key label, CLI output. Use when adding a menu row or binding, when asked to "reword this", "the descriptions are bad", "what should this row say", or when a line reads as a metaphor, a riddle, or an argument for why the project exists. Owns the split between the two voices.
---

# Words on the screen

This project writes in two voices and only one of them ends up on the pad.

| Voice | Where | Job |
|---|---|---|
| **The argument** | comments, `docs/`, `README.md` prose | justify a decision to whoever changes it next |
| **The interface** | `label`, `detail`, `desc`, `short`, CLI output | tell someone holding a pad what happens if they press this |

The failure this skill exists to stop is the argument standing where the
interface should be. It is silent: the row parses, `omapad check` is happy, the
tests pass, and the person on the sofa reads *The couch's television* and still
does not know what the button does.

The standard is [`docs/conventions/writing.md`](../../../docs/conventions/writing.md)
- read it before writing the string, not after review. What follows is the
short form.

## The test

Read the label and the detail together as one line. If **what happens when I
press this** is not in it, or arrives only after a beat of decoding, rewrite it.

```
YouTube · The couch's television     a metaphor to unpack
YouTube · Video                      the answer
```

## The four that catch almost everything

1. **No metaphor, no riddle.** Say what the row does or what is inside it.
2. **No couch, no sofa, no "in your hands", no "from across the room".** That
   is why the row exists, and the reader can see where they are sitting. Keep
   it - in the comment directly above the row, where this project wants it.
3. **No machine words** - axis, evdev, socket, class. Where the mechanism *is*
   the choice, use what is printed on the hardware: *XInput*, *NS mode*, *L1*.
4. **A fragment, not a sentence.** Sentence case, no full stop, never *your*.

Then two that decide whether the line should exist at all:

- **A detail that restates its label is deleted**, not improved. The row is
  drawn a line shorter without it. `Browser` and `Terminal` ship with none.
- **A detail among siblings says the difference, not the definition** - four
  choices under one heading answer *why this one and not the next*.

## Budgets

| Field | Budget | What happens past it |
|---|---|---|
| menu `label` | three words | elides mid-word, silently |
| menu `detail` | ~40 characters | same |
| `desc` | a phrase | the guide wraps |
| `short` | **one word** | the game bar prints only the first |

The 40 comes from `Menu.qml`: a 320 px panel less a 36 px icon and a 14 px
tick, at `bodySmall`. Game mode scales panel and type together, so it holds.

## The reader's word, not ours

The code keeps its own names; do not rename it to match.

| Code | Interface |
|---|---|
| `rumble` | Vibration |
| `osk` | Keyboard |
| `layout`, badge | Button labels |
| `deadzone` | Dead zone |
| the pad | Controller |

And one thing has **one** name across the menu, the guide, the bar and
`README.md`. Two names for one thing is a puzzle handed to the reader.

## Two traps

- **A detail cannot know anything live.** It is written once in a config file.
  The tick and `value(action)` are how a row says what is currently true; see
  the `pad-setting` skill.
- **A line that contradicts the design teaches the wrong model of the whole
  thing.** `Game mode / Hand the pad back to games` was wrong on both counts:
  game mode is the couch environment, and the hand-off is `handover.py` and
  automatic. Check the row against `docs/components/` before writing its detail.

## Verifying

`omapad check` parses the strings; it cannot read them.

```bash
systemctl --user restart omapad
./bin/omapad ctl menu toggle     # walk every level
./bin/omapad ctl guide toggle    # every desc, with the bar's short beside it
```

Read each row once, from where the pad is actually used. A line you read twice,
or one that ends in `…`, is the finding.
