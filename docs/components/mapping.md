# Mapping wizard - `omapad/mapping.py` + `shell-plugin/Mapping.qml`

Which physical button is which printed one.

omapad names buttons by what is printed on the pad and picks a profile from
what the driver reports - two facts that need not agree. The Beitong KP20 is
the case that proved it: in NS mode it sends Switch Pro codes out of a shell
printed with Xbox letters, so every face button answered to its neighbour's
name and `X` produced a right click. A pad nobody has written a profile for is
the same problem with less to go on.

Neither is worth guessing at, so the pad is asked.

## The walk

`STEPS` is the printed names in the order they are asked for: face buttons
first, because they are what a wrong profile scrambles, then outwards to the
ones a pad may not have at all (`OPTIONAL`). The daemon feeds **raw codes**
in - the mapping being fixed is the one that would otherwise do the
translating - through `mapping_press(kind, code)`.

Two rules make it drivable with nothing but the pad:

- **A code already spoken for skips the step.** It is the only gesture
  available when the button being asked for does not exist on this pad (an
  Xbox pad has no Capture), and it doubles as the answer to pressing the same
  button twice. `taken()` is the check.
- **The last step is a confirmation drawn in the pad's new names**, so saving
  is itself a test of what was just learned. Get it wrong and B discards it.

`MappingModel`: `start`, `learn`, `skip`, `back`, `restart`, `confirm`,
`buttons`, `triggers`, `rows`, `view_state`. Holding any button for
`MAPPING_CANCEL_HOLD` seconds (in `daemon.py`) lets go of the pad.

## What it writes

`render(mappings)` writes `~/.config/omapad/mapping.toml`, keyed **per
device identity** - the KP20 alone has two, one per hardware mode. A file of
its own rather than a block in `config.toml`: that one is hand-written and
full of comments a program would trample, and a mapping is undone by deleting
a file rather than by finding the block again.

## Prompts are printed in the layout in force

The names in `STEPS` are the Switch's; a pad printed like an Xbox one carries
`View` where this says `MINUS`. So the screen asks in `guide.badge_of(...)`
(`badge`, `PROMPTS`, `LAYOUT_PROMPTS`) and keeps the logical name for the file
it writes.

## Payload - `mapping.sock`

```
open, step, label, kind, prompt, optional, index, count, confirm, note, pad,
keys: {save, discard, restart}, rows
```

`keys` is in the pad's just-learned names, because on a PlayStation pad "A
saves it" names nothing that is in your hands.

## The panel

`Mapping.qml`. The asked-for name is the largest thing on screen and the list
underneath is a progress report you glance at: eyes are on the pad, not the
screen, and what the screen has to survive is being seen in the corner of one.
The escapes are printed on every step, because none of them can be inferred
from a pad whose map is exactly what is in doubt.

Settings: `[mapping] socket`.
