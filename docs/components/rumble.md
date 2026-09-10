# Rumble - `omapad/rumble.py`

Force feedback: the pad answering a press with a tick you can feel. 120 lines,
and all three of them are constraints.

- **The effect is uploaded once per connection**, not once per pulse. An
  `EVIOCSFF` round trip inside a button press is latency under the thumb.
  `configure()` re-uploads when a strength changes, because that is the only
  way a new level reaches the motor.
- **A tick sends its own stop.** Buzzing and stopping are two packets rather
  than one - an Xbox pad is told to run its motors and runs them until
  something says otherwise - and the second one is the kernel's to send when
  the effect's `replay.length` runs out. It does not always arrive. See below.
- **Every path is best-effort**, the way the view socket is: a pad with no
  motors, a node we may only read, a dongle yanked mid-pulse - none is worth
  more than a log line.

## Surface

`Rumble(config)`, then `attach(device)` on connect, `detach()` on
disconnect, `pulse()` to fire, `settle(now)` every loop tick to end what has
run its length, `available` and `settling` to ask. `_magnitude()` turns the
config's 0..1 into the unsigned 16-bit level the kernel wants.

Settings: `[rumble] enabled`, `strong`, `weak`, `duration_ms`.

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
- A new effect kind would be a second uploaded effect, not a re-upload per
  press.
