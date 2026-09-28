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
cannot sit lower and duller, which says *this one went nowhere*. So the cue
is one note, the A below the commit's D, on the vibraphone with the soft
mallet and muffled: the commit rings out above D and the back stays beneath
it. It shares the tick's note and is told from it by the instrument - a
soft, dull vibraphone against a hard marimba stroke - and by two dB. The commit's two notes falling were tried
first and heard as wrong: a falling figure reads as an error, and leaving
is not one.

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

**`show` is the arrival** ([94](../decisions/94-sounds-measured-where-heard.md)).
A low D and its octave on the vibraphone, soft, swelling in over 25 ms: the
deepest thing a surface says and the slowest to arrive, which is what tells
it from a press landing. A rolled D, F sharp, A was tried first and heard as
a notification. It is Xbox's `Show`; `back` was already its `Hide`. Like `back` it is
said by the **verb** - `menu`, `guide` and `osk`, `open` or `toggle`
when the surface was down - and never by a surface arriving on its own, so the
keyboard that opens itself under a text field says nothing. It ticks the hands
for `back`'s reason.

**`next` and `prev` are which way a page went**: the menu's bar, the guide's
pages, the keyboard's. The move's neighbours on the scale, a little longer,
one up and one down - Xbox's `MoveNext` and `MovePrevious`. They were `move` before, which
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

**They are two bars** ([101](../decisions/101-a-marimba-and-a-vibraphone.md)), modelled
rather than sampled, and which one a voice is on says what kind of thing
happened. **Walking is the marimba** - the move, the page turns and the
tick: a bar with a marimba's carved overtones, the resonator tube under it
that holds the note and blooms, and a hard mallet given as the length of
its push against the wood. **What happens to a surface is the
vibraphone** - it arrives, a press is taken, it is left, it will go no
further: the marimba's metal cousin, tuned 1, 4, 10 and ringing far longer,
its mallet given as which overtones it wakes. Those four were the marimba
first and were heard as the walk repeating itself.

Every cue is a note or a few, from D, E, F sharp and A, so any two that
overlap are consonant: the move E, the page turns F sharp and D, the tick
the A below; the show a low D and its octave swelling in, the commit D and
A struck together hard, the back that A soft and muffled, the edge two
quick low strokes - the shape of *no* - soft and muffled. No pitch slides
anywhere: a glide on a struck note is a water drop, and was heard as
one.

Four decisions shape all of them, and each is in that file beside the number
it produced: under 200 ms, no step at either end that moves the speaker
cone, a body that has rung down before the next press, and nothing whose
loudness lives below what a television's drivers play.

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
