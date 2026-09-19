# 11. A place to see the bindings · ✅ Done · M

Shipped as a third surface — `omapad/guide.py`, `guide.sock`,
`shell-plugin/Guide.qml`, an implicit `[bindings.guide]` layer and
`omapad ctl guide <toggle|open|close|next|prev>` — opened from the menu's
**Shortcuts** row. Read-only, as the write-up wanted: seeing the map is most of
the value, and item 14 already made one key of it editable.

**The buttons are drawn as buttons, not as letters.** That is the whole point
of the surface. `A` in a list is a letter; a round face badge beside a
pill-shaped bumper is the thing under your thumb. So the badge carries the
*shape* — round face buttons, pill shoulders, a trigger with its bottom corners
squared off, a ringed stick, a lozenge for the small system buttons — and takes
its colours from the theme. A console's own palette (green A, red B) would read
as a controller in exactly one Omarchy theme and fight every other one.

- **Grouped by region of the pad, not by config order**: face buttons, D-pad,
  shoulders, sticks, system. That is where a hand looks for a button it has
  forgotten.
- **One page per layer**, walked with `L`/`R`, so the layered map the write-up
  said a flat list handles badly is simply four short pages. omapad packs the
  groups into columns because it is the side that knows when a layer no longer
  fits — a layer taller than two columns becomes `Base 1/2` rather than being
  clipped.
- **A layer that binds nothing gets no page**, and the sticks print their role
  (`Move the pointer`, `Resize the window`) rather than a binding, because that
  is what they carry.
- **It only prints buttons the connected pad has.** `CAPTURE` exists on the
  `nintendo_pro` profile alone, so in XInput mode the row is absent instead of
  lying. The pages are rebuilt when the guide opens, not at startup, since the
  pad can be switched between modes while the daemon runs.
- **The footer is the guide's own layer**, collapsed by what each binding does:
  half the pad closes it, and printing that eight times says nothing eight
  times.

**Descriptions come from the action, with an escape hatch.** `key:ENTER` is
"Enter" and `click:left` is "Left click" without anyone writing that down
twice, and a Lua dispatcher is read back as words. That last one is thin by
nature — `direction = 'u'` is not a sentence — so a binding can say what it
means outright, next to itself:

```toml
L = { tap = "hypr:hl.dsp.focus({ workspace = 'r-1' })", desc = "Previous workspace" }
```

**One bug fell out of that.** A table binding with no `hold` was treated as a
tap/hold pair whose hold did nothing, which waits for the release before firing
— so annotating a plain binding with `desc` would have quietly changed what it
does. A table that names no hold is now the plain binding it replaced.

**Editing it in place is still the second, larger step**, and it stays unbuilt:
a surface you drive with a pad is a poor text editor, and the config is one
file away.
