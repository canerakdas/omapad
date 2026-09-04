# On-screen keyboard - `omapad/osk.py` + `shell-plugin/Keyboard.qml`

The layout, the selection and the modifier latches live in the daemon, so
pressing a key types immediately through the uinput keyboard omapad already
owns. The panel is handed rows, a selected cell and the latch state, and draws
them.

## The layouts

Two sets ship (`LAYOUTS`, `DEFAULT_LAYOUT = "grid"`):

- **`grid`** - a console keyboard: the whole thing on one page, in a fixed
  width budget every row shares. It used to insist on even columns, on the
  grounds that a D-pad walks a uniform grid predictably - but `move_vertical`
  carries the horizontal *position* rather than the column index, so a wide
  Tab or Enter costs nothing in navigation. The keys are sized the way a real
  keyboard sizes them, and the per-row budget is what keeps the columns lining
  up.
- **`classic`** - a physical desktop keyboard, staggered widths and all, for
  when familiarity matters more than navigation.

A key is `_k(label, shifted, action, weight, special, alt)`. Actions:
`"KEYNAME"` / `"SHIFT+KEYNAME"` types, `mod:<name>` latches, `layer:<name>`
switches page (`next`/`prev` turn it), `text:<string>` types a string, `close`
puts the keyboard away.

**Shift does two jobs.** On a character key it swaps the character. On a key
with an `alt` action it swaps the whole key - Shift over the arrows turns
left/right into up/down, which is what lets four arrows live in two cells.

## The page an app lends

An application profile can lend a page of its own for as long as its window is
focused (`set_app_page`, `clear_app_page`, `app_page_rows`, `APP_LAYER`).
It is built from what the profile handed over rather than written into a
layout, so **how many pages the keyboard has is a property of the model** and
the page-turn cell reads its name back out of it.

The daemon fills it (`osk_app_entries`, `refill_osk_app_page`). A page with a
`from` command is read when the keyboard opens and kept for its `ttl` -
opening it twice to type two commands should not re-read a history file that
nothing has written to in between. Past the ttl the command runs off the loop,
so the keyboard opens on the page's own keys, or on what it held last, and
takes the fresh reading when it lands: a shell history that is slow to read
must not be a keyboard that is slow to appear. One reading in flight per
profile, and an answer for an app that is no longer in front is dropped.

## `OskModel`

`move_horizontal`/`move_vertical` walk, `set_layer`/`cycle_layer` turn the
page, `latch`/`hold`/`toggle_caps`/`clear_latches` are the modifiers, `press()`
fires the current key, `set_labels()` takes what
[`xkb.md`](xkb.md) read back, `set_badges()` takes which pad button reaches
which cell (`badge_index`).

`apply_overrides()` applies `[osk.keys]`, raising `OverrideError` for a key
that is not there.

## Payload - `osk.sock`

```
open, layout, layer, balign, sel: [row, col], mods: {shift, ctrl, alt, caps},
rows: [[ {l, x, w, s, g, m, b?, k?} ]]
```

`l` label, `x` what Shift makes of it (empty on letters - printing `Q` over
every `q` is twenty-six hints for the one thing every keyboard already
teaches), `w` weight, `s` special, `g` a one-character symbol that must stay at
character size, `m` the modifier it latches, `b`/`k` the controller badge that
reaches it - absent where no button does.

## The panel

`Keyboard.qml`. Overlay layer, no keyboard focus, empty input region, and
`ExclusionMode.Normal` with an `exclusiveZone` of its own height - it is the
one surface that reserves space, so it does not cover what is being typed
into.

Settings: `[osk] layout`, `badges`, `badge_align`, `repeat_delay_ms`,
`repeat_rate_ms`, `labels_follow_layout`, `socket`, plus `[osk.keys]` and
`[bindings.osk]`.
