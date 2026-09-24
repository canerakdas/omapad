# Rumble - `omapad/rumble.py`

Force feedback: the pad answering a press with something you can feel. Four
constraints.

- **Effects are uploaded once per connection**, not once per pulse. An
  `EVIOCSFF` round trip inside a button press is latency under the thumb.
  `configure()` re-uploads when a strength changes, because that is the only
  way a new level reaches the motor.
- **A pulse sends its own stop.** Buzzing and stopping are two packets rather
  than one - an Xbox pad is told to run its motors and runs them until
  something says otherwise - and the second one is the kernel's to send when
  the effect's `replay.length` runs out. It does not always arrive. See below.
- **There are four effects, not one.** A pad that answers everything with the
  same tick is a pad saying nothing.
- **Every path is best-effort**, the way the view socket is: a pad with no
  motors, a node we may only read, a dongle yanked mid-pulse - none is worth
  more than a log line.

## The vocabulary

Four words, uploaded once at `attach()`, in `VOCABULARY`:

| Word | Says | Waveform | Fired by |
|---|---|---|---|
| `tick` | a press landed | `FF_RUMBLE` | a binding's `rumble`, `[snap] rumble`, `[mode] rumble`, the confirmation countdown, the stopwatch's minute mark |
| `edge` | you cannot go further | `FF_SQUARE`, two cycles | a control at its end, the grid's rim, a transport direction the player says is closed |
| `commit` | that took | `FF_TRIANGLE`, one cycle | a switch flipped, a choice walked, a tile picked up or put down |
| `texture` | the push landed, on this side | `FF_RUMBLE`, `replay.length = 0` | **aimed** on the first step of a push, **stopped** by the next step of the same push or when the push settles |

**The waveform is not a setting.** A square wave is what makes an edge feel
like an edge, and making it configurable is offering to turn a bump into a
hum. Strength and length are settings, because those are taste. `cycles` is
the same argument one field along - two cycles is what reads as a bump rather
than a click - so the period is computed from the length rather than named.

**`texture` is the one word with two motors to say something with**, and that
is why it is plain `FF_RUMBLE` where the two words above it are periodic: a
periodic effect carries one magnitude, and one magnitude cannot say a
direction. A pad wires its low-frequency motor on the left and its
high-frequency one on the right, so a value pushed right is felt on the right.

**One level, and the side is the message.** It rose with the distance from
where a push began for a pass, which is a second reading of the number the
tile is already printing - and what a hand pushing a control is asking is
whether the push landed. So `aim(name, side)` takes "left", "right" or "both"
and plays the effect's own strength there: `[rumble] texture_strength`, an
absolute level like `edge_strength` and `commit_strength`.

**A range is the only thing it answers.** A list inside a card had it too for
a while, on the left motor both ways - the D-pad is under that thumb, and a
vertical push has no left and right to answer with. That is the trouble with
it: one motor for both directions is a buzz saying a thing moved without
saying which, which is the scheme this effect was kept switched off for. A
step of a selection is heard and not felt, wherever it is walked.
`daemon.menu_feel(direction)` is the one place that decides the side.

**A control you point at is not a push, and gets none of this.** The word
earns its place two paragraphs above by being *the only thing on the pad that
answers a direction* - and that is a claim about a control you push. An aimed
knob (`[menu] turn = "aim"`) has its direction already: it is the hand's own,
and the ring is under the thumb making it. Worse than redundant, the direction
there is the sign of the last difference rather than of a push, so a thumb
resting two degrees off the end of a scale flips it every frame - measured,
seven motor swaps in eight frames, an `EVIOCSFF` apiece, which is the write
the paragraph below says is skipped. Roadmap 17's rule is the short version:
*a scheme where every press buzzes says nothing.* `edge` stays, because *you
cannot go further* is the one thing there the screen cannot say faster;
`carry` keeps `texture`, because winding really is a push.
`daemon.menu_adjust(feel=False)` is where that is said.

**It is re-uploaded in place while it runs.** `EVIOCSFF` with an effect's own
id replaces what that slot holds, so the level follows the value without a gap
- one round trip per step of a push, which is the thing this file otherwise
refuses. It is allowed here because it *is* the press's own work rather than
something happening underneath one, and because a level that cannot change
while the thumb moves is not a level. The write is skipped where the
magnitudes have not changed, which is most steps of a held repeat.

**Once per push, not for the length of it.** It was held for as long as the
control moved, and a direction held down a slider was a buzz for the whole of
the hold - *titreşim çok fazla oluyor basılı tutunca*. What a hand asks the
motor is whether the push landed, and the first step answers that; after it the
needle on screen is saying the rest. So the first step of a push aims it, the
next step of the same push stops it, and `menu_settle` ends it for a tap - a
tap is felt for the length of `MENU_SCRUB_HOLD`. A trigger sweep never starts
it: a pull is a motion held for as long as the trigger is in, the same buzz one
road along. `edge` still bumps once at the end of the travel.

**It ships on now** (`[rumble] texture = true`), where it shipped off, and it
needs no waveform a pad might not have - so every pad that rumbles at all can
say it. Roadmap 17's rule - *a scheme where every press buzzes says nothing* -
is what kept the old hum switched off, and it still would: a buzz that says
*which way you just pushed* is not a press buzzing, it is the only thing on
the pad that answers a direction.

**Nothing buzzes on a plain move.** Not a tile to the next tile, not a chip to
the next chip, not a row to the next row inside a card. `[snap] rumble`'s comment is the older half of the same rule -
*a step that repeats while it is held would buzz all the way down a list* -
which is also why a scrubbing control does not tick per step: it is felt once,
on the first step of the push, and not again until the push has stopped. A *pointed-at* control holds none at all, for the
reason above.

**And that is one of the two places the speakers say something the motor
cannot.** [`sound.md`](sound.md) carries the same three played words, said at
the same call site by `daemon.say()`, plus two of its own. `move` is this
paragraph: a step repeating under a held direction buzzes and the same step
*ticks*, because a sound decays and a vibration does not - so a selection
walking a page is heard and never felt, and `say(name, rumble=False)` is what
that asymmetry looks like in the code.

`back` is the other, and it is the opposite asymmetry: it *does* tick, because
a press is a press and the hands have no business finding out that something
was cancelled by feeling nothing. What the motor cannot do is be **lower**. It
can be shorter or weaker, which says *less happened*; only a pitch falling
where another rose says *this one went the other way*. So `say()` maps both
`move` and `back` onto the motor's `tick` - they are the two words
`VOCABULARY` does not hold - and the speakers are what tell the two presses
apart. Nothing here changes: the motor's rule is still the motor's.

## Surface

`Rumble(config)`, then `attach(device)` on connect and `detach()` on
disconnect. `play(name)` fires a pulse and `pulse()` is `play("tick")` under
its old name, so nothing that called it changed. `start(name)` / `stop(name)`
begin and end a held effect, both idempotent, and `aim(name, side)` holds one
on "left", "right" or "both" at that effect's own strength - anything else
stops it.
`stop_held()` ends everything still running, which is what
`release_everything()` owes the motor.
`settle(now)` every loop tick ends a pulse that has run its length - a held
effect has no length to run out, so nothing there can cut one short.
`available` asks whether anything is uploaded, `has(name)` whether this pad
took that word.

`plan(levels, supported, slots)` is a pure function saying which words a pad
will take and with which waveform. `attach()` uploads what it returns and
`omapad check` prints it, so the report is about the pad the daemon has rather
than a second opinion about it. `_magnitude()` turns 0..1 into the unsigned
16-bit level rumble wants; `_amplitude()` into the **signed** one a periodic
effect wants, which tops out at `0x7FFF`.

Settings: `[rumble] enabled`, `strong`, `weak`, `duration_ms`, `floor_ms`,
`edge_strength`, `edge_duration_ms`, `commit_strength`, `commit_duration_ms`,
`texture`, `texture_strength`.

`[rumble] floor_ms` is the floor under every pulse, and it is stated for what
it is: the shortest thing worth asking for, because a pulse shorter than the
packet interval of the slowest driver omapad supports can fall between two
packets and never reach the motor - `hid-nintendo` sends rumble every 50 ms.
It is not a claim about any one pad.

## How many the pad will hold

`EVIOCGEFFECTS` says how many effects the device takes at once, asked rather
than assumed: uploading past it fails with `ENOSPC` on the effect nobody
notices is missing. `EFFECTS` is the upload order and therefore the priority -
a pad with fewer slots than words keeps the ones nearest a plain press, and
says in `journalctl` which it could not take. A driver that will not answer
the ioctl is assumed to hold one, which is what every rumble pad has.

A re-attach never reuses an id: `detach()` clears the table whether or not the
erase went through, because a pad that has gone away comes back with a fresh
slot table and an id remembered across that names somebody else's effect.

## The tick that sticks on

Reported from the couch: a shoulder held in a game or in a browser announces
its hold with a tick, and the tick never stops - until the next thing that
buzzes anything ends it. Both places have a second force-feedback client
playing effects of its own into the same device, which is what the desktop
does not.

Nothing above the kernel can see which stop went missing, so the tick stops
being anybody else's job: `pulse()` writes down when the buzz is due to end,
and `settle()` writes the stop itself `SETTLE_MARGIN` after that. The write is
also what makes the kernel look at every effect on the device again, so an
effect that has outlived its own length - ours or an app's - ends there too.

`daemon.needs_tick()` counts a tick owed a stop, so the loop stays at frame
rate until it goes out; on the 250 ms idle poll a 60 ms click would read as a
buzz.

## Rules

- Nothing here decides *when* to buzz. The daemon does, from the binding, from
  `[snap] rumble` and from `[mode] rumble` - the mode switch, whose result is
  across the room rather than under the thumb.
- **One of them answers no press at all**: `[chrono] rumble` ticks when a
  running stopwatch's sweep hand comes back to twelve
  ([`chrono.md`](chrono.md)). The motor alone rather than `say()`, because
  there was nothing to answer: a noise made at somebody once a minute for as
  long as a measurement is left running is a machine talking to itself.
- A new effect kind is **a fifth entry in `VOCABULARY`**, uploaded at attach
  beside the other four. Never a re-upload per press, and never a parameter
  passed to `play()`.
- A held effect is a finger's, the same as a held key. Anything that lets go
  of everything lets go of it too.
