# 54. A head cell that could say the time and not who you are · ✅ Done · M

Asked for from the sofa: *konumu kaldıralım, derece yerine ikon kullansak olur
mu, ek olarak saatin üstüne de kullanıcı adını yazabilir miyiz.*

Three asks, and the third one found the fault. Item 53 gave a head cell a
second line, `under`, and made it a strftime format - which was right for a
weekday and useless for a name. **A cell could print what a command said while
the line under it could only print a time**: two grammars wearing one name, and
the first thing anybody wanted there was the one it did not have.

So every line of a cell is the same kind of thing now. `over` above, the cell's
own line in the middle, `under` below, and each is a `format` or a `from`:

```toml
[[menu.head]]
span = [2, 3]
over = { from = "id -un", ttl = 0 }
format = "%H:%M"
under = "%A"
```

A bare string is still a format - `under = "%A"` is the whole of what a weekday
costs - and a table is the long form. It is a *simplification*: the old rule
that refused `under` beside a `from` is gone, because there is nothing left to
refuse.

- **Three lines in one cell, not three cells.** The head packs first fit, so
  nothing could promise that the cell holding the day landed under the one
  holding the time rather than beside it. Tried as three cells first, and the
  screen said so at once: a cell is a sixth of the card wide and its text is
  flush left, so an icon in its own cell sat a cell's width from the reading it
  belonged to.
- **`head_sources(cell)` is the one thing that knows a cell has three lines**,
  so the daemon asks for what has gone stale without learning the shape of a
  cell, and each line files its answer under a name derived from the cell's.
- **`ttl = 0` now means what `build_head` always said it meant.** The docstring
  read *zero asks once* and the code asked again every second, which nothing
  had noticed because nothing shipped with one. A name is exactly that case, so
  a zero-ttl line that answers is kept for the session - and the *never again*
  is written when the answer lands rather than when it is asked for, so a
  command that failed is tried again instead of leaving the cell empty until
  the daemon restarts.

**And the weather cell says less, in Omarchy's own glyph.** The place goes -
you know where you are - and so do the words `Temp` and `Wind`, the first
replaced by `omarchy-weather-icon` and the second by the arrow that was already
after it:

```
Istanbul  ·  Temp 20°C  ·  Wind ↓15km/h    →     20°C  ·  ↓15km/h
```

**`omarchy-weather-icon` is the whole reason this stays inside the rule.** A
live condition icon means knowing the condition, and `omarchy-weather-status`
never prints it - so the honest options looked like omapad querying wttr.in
itself, which is the network, the location and the cache that 23 refused. The
helper already owns all three, and it is day/night aware on top.
Nothing was taken on; a second command was added to a string in the config.

The two run as a **pipeline** rather than one after the other, so their network
calls overlap: half a second against `list_timeout_ms`'s one, where sequentially
they came to eight tenths. `omarchy-weather-status | { i=$(omarchy-weather-icon);
sed ...; }` - both sides of a pipe start at once, which is the whole trick. What
the `sed` does is wording, which *is* omapad's business where the lookup is not,
and a failure has no place, no `Temp` and no `Wind` in it, so the sentence the
helper wrote passes straight through.
