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
| `tick` | a press landed | `FF_RUMBLE` | a binding's `rumble`, `[snap] rumble`, `[mode] rumble`, the confirmation countdown |
| `edge` | you cannot go further | `FF_SQUARE`, two cycles | a control at its end, the grid's rim, a transport direction the player says is closed |
| `commit` | that took | `FF_TRIANGLE`, one cycle | a switch flipped, a choice walked, a tile picked up or put down |
| `texture` | it is moving | `FF_SINE`, `replay.length = 0` | **started** when a scrub begins, **stopped** when it ends |

**The waveform is not a setting.** A square wave is what makes an edge feel
like an edge, and making it configurable is offering to turn a bump into a
hum. Strength and length are settings, because those are taste. `cycles` is
the same argument one field along - two cycles is what reads as a bump rather
than a click - so the period is computed from the length rather than named.

**`texture` has no fallback, and the other three do.** Where a pad has no
periodic effects `edge` and `commit` are played as plain ticks; `texture` is
simply unavailable. Degrading a *continuous* effect onto one that has to be
stopped is the tick that sticks on arriving through a new door, and a hum
stuck on is not the same risk as a click stuck on.

**`texture` ships off** (`[rumble] texture = false`). Roadmap 17's rule - *a
scheme where every press buzzes says nothing* - applied to the newest gesture:
it is the likeliest of the four to annoy, and the default says so.

**Nothing buzzes on a plain move.** Not a tile to the next tile, not a chip to
the next chip. `[snap] rumble`'s comment is the older half of the same rule -
*a step that repeats while it is held would buzz all the way down a list* -
which is also why a scrubbing control does not tick per step: it holds one
continuous `texture` and stops it when the direction is let go.

## Surface

`Rumble(config)`, then `attach(device)` on connect and `detach()` on
disconnect. `play(name)` fires a pulse and `pulse()` is `play("tick")` under
its old name, so nothing that called it changed. `start(name)` / `stop(name)`
begin and end a held effect, both idempotent; `stop_held()` ends everything
still running, which is what `release_everything()` owes the motor.
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
- A new effect kind is **a fifth entry in `VOCABULARY`**, uploaded at attach
  beside the other four. Never a re-upload per press, and never a parameter
  passed to `play()`.
- A held effect is a finger's, the same as a held key. Anything that lets go
  of everything lets go of it too.
