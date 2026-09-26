# The sounds - `omapad/sound.py` + `shell-plugin/Sound.qml`

| | |
|---|---|
| **Daemon** | `omapad/sound.py` (the cue), `assets/sounds.py` (the files) |
| **Panel** | `shell-plugin/Sound.qml`, `shell-plugin/SoundBank.qml` |
| **Socket** | `sound.sock` |
| **Settings** | `[sound] enabled`, `volume`, `pack`, `socket` |
| **Verb** | `omapad ctl sound <move\|prev\|next\|show\|back\|tick\|edge\|commit>` |

A press is answered three ways and this program had two of them. The screen is
answered by looking at it, which is the one thing somebody walking a menu by
thumb is not always doing. The motor is in the hands, so it says nothing while
the pad is on a knee, nothing on a pad that has no motor, and nothing for
anybody who has turned it off. This is the third, and it is the only one a
room hears.

## The vocabulary, and the words that are not the motor's

`VOICES` is `("move", "prev", "next", "show", "back", "tick", "edge",
"commit")`, in the order of what each costs. Three of them are
[`rumble.md`](rumble.md)'s own words, deliberately: **what happened has one
name and two things that can say it**, and `daemon.say()` is where both are
said at once. Two vocabularies kept in step by hand are two vocabularies that
stop being in step.

`move` is the addition, and it is the whole argument for this component
existing rather than being a second switch on the motor:

> A motor that ticked on every step of a held direction buzzes all the way
> down a list - which is what `[snap] rumble` exists to turn off. A speaker
> doing the same thing ticks, because a sound decays and a vibration does
> not.

So the selection walking a grid is **heard and never felt**: `say("move",
rumble=False)` from the three places a selection walks - the menu's tiles, the
menu's bar, the keyboard's keys and the guide's pages. It is the one cue that
has no motor half.

`back` is the second addition, and it is the other kind of thing a motor
cannot be. A motor can be shorter or weaker, which says *less happened*; it
cannot fall a fourth, which says *this one went the other way*. So the cue is
the commit's own note and the commit's own interval inverted - that one bends
up over its length, this one bends down from the same place - and softer and
shorter besides. The pair is one gesture read in two directions, which is what
lets a room tell them apart without anybody having been taught to.

Unlike `move` it **does** tick the motor: a press is a press, and the hands
have no business finding out that something was cancelled by feeling nothing.
`say()` maps it - and `move` with it - to the motor's `tick`, because those
are the two words `rumble.VOCABULARY` does not hold.

Where it is said is the *verb*, never the surface going away: `menu:back`,
`menu:close`, `osk:close` and `osk:toggle` on the way out, `guide:close`,
a control put back with B, and either kind of countdown backed out of
(`cancel_confirm`, `menu_disarm`). A row that ran and took the menu with it
does **not** come through any of them - it has an answer of its own, and two
sounds for one press is one of them arguing with the other.

**`show` is `back` upside down** ([94](../decisions/94-sounds-measured-where-heard.md)).
It rises from A to D - the fourth `back` falls, ending on the note every sound
inside a surface starts on - and it swells rather than strikes, which is what
tells it from the commit's rising fourth: a surface arriving is not a press
landing. It is Xbox's `Show`; `back` was already its `Hide`. Like `back` it is
said by the **verb** - `menu`, `quick`, `guide` and `osk`, `open` or `toggle`
when the surface was down - and never by a surface arriving on its own, so the
keyboard that opens itself under a text field says nothing. It ticks the hands
for `back`'s reason.

**`next` and `prev` are which way a page went**: the menu's bar, the guide's
pages, the keyboard's. The move's note, a little longer, bent a tone up or
down - Xbox's `MoveNext` and `MovePrevious`. They were `move` before, which
said a page turned and not which way. `sound.UNFELT` holds them with `move`:
a shoulder held down turns page after page, and `say()` never sends any of
the three to the motor.

**A mute is said with the same pair.** A `live:` switch whose reading says
`quiets` - `mute`, `mic`, `deafen` - falls as it goes on and rises as it goes
off, `back` and `commit`, which is the shape of Discord's own mute and unmute
and needs no voice of its own (`daemon.live_switch`). A switch that silences
the **speakers** is the one case where the cue and the thing it announces
share a wire: the mute is held `QUIET_AFTER` so the cue is heard first, and an
unmute is sent first and said when the helper has answered.

`texture` is the other direction and will never be here. It is the motor's one
held effect - and the one thing a speaker could not say anyway, because what it
says is *which way and how far*, which is two motors rather than a pitch. A
speaker holding a note under a slider for a second and a half is also the
loudest thing in the room. `tests/test_sound.py` says so as an
invariant rather than as a comment: every *played* word of the motor's
vocabulary is a voice, and the difference between the two sets is exactly
the words this section names.

## It ships off

Every other answer this program gives is to the person holding the pad. This
one is to everybody else in the room as well, so a desktop that started
clicking because a controller had been plugged into it would be omapad
deciding something about the room rather than about the pad. Rumble ships on
for the same reason read the other way.

Two doors, both one press: **Controller ▸ Sounds** on the pad, or
`enabled = true` in `[sound]`. The pair on that page is a pair on purpose -
the motor's switch and this one beside it - because somebody turning one off
is usually choosing between them.

## An event, not a state

`ripple.py`'s shape, for `ripple.py`'s reasons, and they are worth repeating
because they are the two rules this surface breaks:

- **No heartbeat.** Every other surface is re-sent every `VIEW_HEARTBEAT`
  seconds so a restarted shell repaints itself. A sound that is over has
  nothing to repaint, and re-sending it would play it twice a second forever.
- **No `open`.** What the panel watches is `n`, assigned last. A line
  carrying a sequence number already played is a duplicate rather than a
  second press, and the count starts at 1 so a shell connecting mid-session
  does not announce a press that happened before it came up.

The cost of having no heartbeat is that **every line carries the volume and
the pack**, because there is no other line they could arrive on. That is also
why `apply_setting` says a word again when either of them changes: the cue is
the carrier, and `tick` is a reasonable thing to hear when you have just
changed how loud a tick is.

It does **not** go through `scaled()`. Nothing here is drawn, so a scale, a
badge style and whether a bar is up would be three answers to questions this
payload does not ask.

## The payload

`sound.sock`, one line per cue, and no line at any other time:

```json
{"n": 41, "c": "commit", "gain": 0.6, "dir": ""}
```

`dir` empty is the set that ships. Anything else is a directory the panel
opens `<voice>.wav` in, one per word of `VOICES` - expanded in `config.py`,
because the plugin has no shell to expand a `~` with.

## The panel, and the import that is quarantined

Playing a sound needs QtMultimedia, and **Quickshell does not depend on it**.
A QML import that cannot be resolved takes its whole file down, so the import
lives alone in `SoundBank.qml` and `Sound.qml` reaches it through a `Loader`.
On a machine with no `qt6-multimedia` the loader reports an error, the panel
keeps parsing its socket, and every other surface in the plugin is untouched:
a desktop losing its click is not a desktop losing its keyboard.
`omarchy-shell ipc call omapad-sound state` is what answers which of the two
happened.

`SoundEffect` rather than `MediaPlayer`, and that is the whole reason a cue
can answer a press at all: it decodes once when its source is set and keeps
the samples, so firing it is a memory read. A `MediaPlayer` opens a pipeline
per play and lands tens of milliseconds after the button, by which time the
thumb has moved on and the sound is answering the wrong press.

A name the pack does not hold falls back to the shipped file rather than going
silent, which is what makes a pack of one sound worth writing.

## The files

One WAV per voice under `assets/sounds/`, **generated and checked in** exactly as the
badges are - `python3 assets/sounds.py` writes them, and
`tests/test_sound.py` fails when they and the generator disagree. Synthesised
rather than recorded: a sample is a licence to carry and a file nobody can
edit, while these are a table of numbers, so a different commit sound is a
different number in `VOICES` and a re-run.

Four decisions shape all of them, and each is in that file beside the number
it produced: under 100 ms, no attack that steps the speaker cone, an
exponential decay that is over before the next press, and a pitch low enough
for a television's own drivers. The three notes a press produces in a row -
move, move, commit - are a fifth apart, so walking a page and pressing
something sounds like one instrument rather than three unrelated beeps.

**How loud each is, is measured.** Every voice names a loudness in LUFS -
ITU-R BS.1770, the meter every broadcast loudness rule is written against -
measured over one 400 ms block and **through a television**: a fourth-order
high-pass at 200 Hz standing in for a set's own drivers. `render()` scales
each voice until it reads its number. They rise in `VOICES` order, two LU
apart at the least, and `prev` / `next` share one because they are one
gesture ([94](../decisions/94-sounds-measured-where-heard.md)).
`tests/test_sound.py` holds the files to their numbers, the order, a peak
ceiling, and a meter that reproduces the standard's own coefficients and its
-3.01 check tone.

`python3 assets/sounds.py --measure DIR` reads a pack of your own the same
way and prints, per file, the gain that would put it where the shipped voice
is.

## Changing it

Read [`../procedures/pad-surface.md`](../procedures/pad-surface.md) first.
Adding a voice is five places and not one: a name in `sound.VOICES` (and
`sound.UNFELT` if it repeats under a held button), an entry in
`assets/sounds.py` with a comment saying what it is answering and a `lufs`
that keeps the order, the generated file, the list in `SoundBank.qml`, and a
`say()` at the moment it happens. A voice that can be added by touching one file is one that ships
without a sound.

Related: [`rumble.md`](rumble.md) for the other half of the same sentence,
[`ripple.md`](ripple.md) for the shape this borrowed,
[`viewsock.md`](viewsock.md) for why a push never raises.
