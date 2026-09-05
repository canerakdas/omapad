# The words the user reads

Rules here are normative in the same way the language guides are; see
[`README.md`](README.md) for how MUST / SHOULD / MAY are meant. They apply to
every string a person can read on screen or in a terminal: a menu `label` and
`detail`, a binding's `desc` / `short`, a keyboard key `label`, a guide page
title, what `omapad check` prints, and every example a user is told to copy out
of `README.md`.

This project writes in two voices, and only one of them is this one.

| Voice | Where it lives | What it does |
|---|---|---|
| **The argument** | comments, `docs/`, `README.md` prose, commit messages | justifies a decision to whoever changes it next - the couch, the sofa, the pointer that is too slow, what a console does and a desktop does not |
| **The interface** | `label`, `detail`, `desc`, `short`, CLI output | tells someone holding a pad what happens if they press this |

The argument is why this project exists and it is written at length everywhere
else. **It MUST NOT leak into the interface.** A person reading a menu row is
three metres from the screen with a thumb on the D-pad; they are not being
persuaded, they are choosing. `YouTube / The couch's television` is the
argument standing where the interface should be: it is a good sentence about
why the row exists and it is no help at all to the person about to press it.

## The test

Read the label and the detail together, out loud, as one line. If **what
happens when I press this** is not in it - or arrives only after a beat of
decoding - it fails.

```
YouTube · The couch's television     needs the beat, and a metaphor to unpack
YouTube · Video                      does not
```

## Rules

1. **A `detail` MUST say what the row does, or what is inside it.** NEVER a
   metaphor, a riddle, or a description of how the thing feels. `Vibration /
   The tick under your thumb` says nothing the label had not; `Vibration / On,
   off, and how hard` says what the four rows behind it are.

2. **NEVER put our vocabulary for the reader's situation in the interface** -
   *the couch*, *a sofa*, *from across the room*, *in your hands*. It is the
   reason a decision was made, never information: the reader can see where they
   are sitting. Those words belong in the comment beside the row, in `docs/`
   and in `README.md`, and this project is generous with them there.

3. **NEVER the machine's vocabulary either** - *evdev*, *axis*, *uinput*,
   *socket*, *window class*, *dispatcher*. Where the mechanism genuinely **is**
   the choice, name it in the words printed on the hardware or its box -
   *XInput*, *NS mode*, *L1*, *Switch Pro*. Those are the reader's words too.
   `Xbox / The triggers arrive as axes` describes our parser; `Xbox / An XInput
   pad - most of them` describes the thing in their hands.

4. **The interface uses the reader's word; the code keeps ours.** The two do
   not have to match, and where they differ the code is not renamed to follow.

   | The code says | The interface says |
   |---|---|
   | `rumble` | Vibration |
   | `osk` | Keyboard |
   | `layout`, badge | Button labels |
   | `deadzone` | Dead zone |
   | the pad | Controller |
   | `mode:game` | Game mode |

5. **A fragment, not a sentence.** Sentence case, capital first word, **no full
   stop**, no *This will…*, and NEVER *your*: a possessive turns a label into a
   sentence and adds nothing to it. `Drive volume and playback from here` is a
   sentence; `Volume and playback` is the row.

6. **A `detail` MUST NOT restate its label.** A row that carries one is drawn a
   line taller (`detailRowHeight` in `Menu.qml`), so a detail that adds nothing
   costs both height and a second thing to read. Delete it - `Browser` and
   `Terminal` ship without one. **Exception:** a run of sibling rows MAY keep
   parallel details where one alone would be dropped, because the column is
   then read as a column - the four app rows say *Big Picture · Voice chat ·
   Music · Video*, and dropping the weakest of the four breaks the row of them.

7. **A choice row's `detail` is the difference from its siblings**, not a
   definition. Under `Button labels`, `Nintendo / A B X Y, ZL and ZR, − and +`
   answers *why this one and not the row under it* - which is the only question
   a list of four choices asks.

8. **A `detail` cannot know anything live.** It is written once into a config
   file. Anything that depends on state is the daemon's: the tick for a setting
   in force, and `value(action)` for a stepping row, which replaces the detail
   with where the number has got to.

9. **The interface MUST NOT contradict the design.** `Game mode / Hand the pad
   back to games` was wrong on the pad and wrong in the manual: game mode is
   the couch environment, and handing the pad to a game is `handover.py`, is
   automatic, and is not this row. A wrong line here teaches a wrong model of
   the whole thing.

10. **Budget: about 40 characters for a `detail`, three words for a `label`.**
    Past that the text elides, silently and mid-word. Derived from the panel:
    `Menu.qml` caps the menu at 320 logical px, an icon takes 36 and the tick
    14, and the detail is drawn at `bodySmall` - 11 px at the shipped scale.
    Game mode scales the panel and the type together, so the budget in
    characters does not change with it.

11. **A row that acts takes an imperative; a row that opens a place takes a
    noun.** `Close window`, `Remap the buttons`; `Audio`, `Display`,
    `Shortcuts`. A submenu label MUST NOT be a verb phrase - it does not do
    anything, it goes somewhere.

12. **British spelling** - *centre*, *behaviour*, *recognise* - except where an
    API name demands otherwise (`hl.dsp.window.center()`,
    `Text.AlignHCenter`). Measured: 94 British spellings against 54 American,
    and all 54 are API names.

13. **One thing has one name everywhere.** Whatever the menu calls it, the
    guide, the game bar, `README.md` and the settings file call it the same:
    *dead zone*, never *deadzone* or *threshold* in the same breath. A reader
    who has to work out that two words are one thing has been given a puzzle
    instead of a manual.

## What a good one already looks like

The binding `desc` strings did not drift and are the model: `Previous
workspace`, `Close the window`, `Jump to a channel`, `Deafen - mic and sound`.
Verb or noun, no metaphor, no *you*, no argument. `short` is the same rule with
one word to do it in - and it is required whenever the first word of `desc` is
not the meaning, because the game bar prints only that word
([`bindings.md`](bindings.md)).

## The ledger: what this standard changed when it was written

| Where | Was | Is | Rule |
|---|---|---|---|
| `YouTube` | The couch's television | Video | 2 |
| `Fullscreen` | What a game hidden behind Steam needs | Make it fill the screen | 1 |
| `Controller` | The pad in your hands | Speed, vibration, labels, mapping | 1, 5 |
| `Vibration` | The tick under your thumb | On, off, and how hard | 1, 5 |
| `Speed` | How fast the two thumbs are | How fast the sticks move | 1 |
| `Dead zone` | How much of a stick does nothing | Stick travel that does nothing | 1 |
| `Scale up` | Bigger desktop, for the couch | Bigger text and windows | 2 |
| `Apps` | Open something | Steam, chat, music, video | 1 |
| `Filled` | The label set on a washed shape | Letter on a soft-filled shape | 3 |
| `Stencil` | The label punched through a solid one | Letter punched out of a solid shape | 1 |
| `PlayStation` | The shapes, L1 and L2, Create and Options | Shapes, L1 and L2, Create and Options | 10 |
| `Xbox` (profile) | The triggers arrive as axes | An XInput pad - most of them | 3 |
| `Follow the pad` | Whatever the profile prints | What the pad reports it is | 3 |
| `Close the window in front` (label) | - | `Close window` | 10, 11 |
| `lock:` - the row, the guide page, the notification | Game lock | Workspace lock | 9, 13 |

## Checking it

`omapad check` parses the rows; it cannot read them. The check is the room:

```bash
systemctl --user restart omapad
./bin/omapad ctl menu toggle     # walk every level
./bin/omapad ctl guide toggle    # every desc, and the bar's short beside it
```

Sit where the pad is used and read each row once. A line you have to read
twice, or that ends in `…`, is the finding.
