# Rumble - `omapad/rumble.py`

Force feedback: the pad answering a press with a tick you can feel. 86 lines,
and both of them are constraints.

- **The effect is uploaded once per connection**, not once per pulse. An
  `EVIOCSFF` round trip inside a button press is latency under the thumb.
  `configure()` re-uploads when a strength changes, because that is the only
  way a new level reaches the motor.
- **Every path is best-effort**, the way the view socket is: a pad with no
  motors, a node we may only read, a dongle yanked mid-pulse - none is worth
  more than a log line.

## Surface

`Rumble(config)`, then `attach(device)` on connect, `detach()` on
disconnect, `pulse()` to fire, `available` to ask. `_magnitude()` turns the
config's 0..1 into the unsigned 16-bit level the kernel wants.

Settings: `[rumble] enabled`, `strong`, `weak`, `duration_ms`.

## Rules

- Nothing here decides *when* to buzz. The daemon does, from the binding, from
  `[snap] rumble` and from `[mode] rumble` - the mode switch, whose result is
  across the room rather than under the thumb.
- A new effect kind would be a second uploaded effect, not a re-upload per
  press.
