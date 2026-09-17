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
switches page (`next`/`prev` turn it), `text:<string>` types a string,
`dictate` hands the typing to a microphone, `close` puts the keyboard away.

**Shift does two jobs.** On a character key it swaps the character. On a key
with an `alt` action it swaps the whole key - Shift over the arrows turns
left/right into up/down, which is what lets four arrows live in two cells.

## The key that types nothing

One cell of the bottom row runs a command instead: `DICTATE`, drawn as a
microphone. A sentence spoken is a sentence nobody walked letter by letter
with a thumb, which is the slowest thing the keyboard asks of anybody.

The split is the usual one. `osk.py` knows the key exists, that it has no
chord, and what it is lit for (`set_dictating`, one of `DICTATE_STATES` -
`on` while the microphone is open, `busy` while what was said is still
becoming text). Everything outside is the daemon's: `[osk] dictate` is the
command, `start_dictation()` spawns it (and `talk()` the two halves of
`talk_start` / `talk_stop`), and `dictate_refresh()` reads
`[osk] dictate_state` on the loop - one word on tmpfs, `DICTATE_WORDS` maps
the tool's vocabulary onto the two the key draws, and an unknown word is
taken as work going on rather than as nothing happening.

**The key is only built where the command can work.** `config.py` empties
`osk_dictate` when the first word of it is not a program on the machine, and
the model is then built with `dictate=False`: `without_dictation()` drops the
key and gives its cell back to the space bar, because every row of a page
spends the same width budget and that is what lines the columns up.

Polling rather than a watch: there is no inotify in the standard library, and
`DICTATE_POLL` (0.2 s, while the keyboard is up) is the trade-off between a
key that lights late and a file the loop opens for nothing. It is read once
more in `set_osk(True)`, because dictation outlives the keyboard - the
compositor has its own hotkey for it - so a keyboard opened over an open
microphone has to come up already lit.

## The hold that lasts

`osk:dictate` is a switch, which is all a key walked to with a D-pad can be -
A is already doing the pressing. `osk:talk` is the other gesture, and the
first action in the tree that **lasts as long as the button**: press runs
`[osk] talk_start`, release runs `talk_stop`, and the shipped scheme puts it
on a hold of MINUS in both `[bindings.base]` and `[bindings.osk]`.

Two commands rather than the toggle, because a gesture that ends when a finger
lifts cannot ask the tool which way it is currently pointing - a toggle out of
step once stays out of step.

**`Action.spans_hold` is what makes it possible, and it is opt-in for a
reason.** `Binding.holdable` is `not is_tap_hold and tap.holdable`, so the
hold half of a pair has always gone through `fire_once` - press and release
together, no interval to speak in (roadmap #29 hit exactly this and shelved
the assistant's `talk`). Making every holdable action span its hold instead
would have changed four shipped bindings: `hold = "key:ENTER"` means one
Enter, and one that lasted would reach the compositor's key repeat. So the
action says whether it lasts, and `check_hold_timers` sets `held.action` to
the hold half; `release_binding` already releases whatever that names.

Two consequences, both written down where they are enforced: `confirm` beside
a spanning hold raises `ActionError` (the announced hold counts down and
*then* runs, so there is nothing left to last for), and `click_button(half=
"hold")` refuses one - a pointer click has no interval, and firing it would
open the microphone and close it in the same breath, which records nothing and
looks exactly like it worked.

`osk:dictate` reaches the switch from a binding and from `omapad ctl osk
dictate` (and `osk talk` / `osk talk off` drive the hold, where there is no
button to come off), and
`binding_target()` maps that onto the key so a bound button is badged on it. It
is the one `osk:` command answered **before** `osk_command`'s "the keyboard is
down" guard: the rest of them navigate a surface and this one does not need
one, so it is a binding worth having on the base layer as well.

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
rows: [[ {l, x, w, s, g, m, d?, b?, k?} ]]
```

`l` label, `x` what Shift makes of it (empty on letters - printing `Q` over
every `q` is twenty-six hints for the one thing every keyboard already
teaches), `w` weight, `s` special, `g` a one-character symbol that must stay at
character size, `m` the modifier it latches, `d` what the microphone key is doing (`on` or
`busy`, absent otherwise - every other key, and that key while nothing is
happening), `b`/`k` the controller badge that reaches it - absent where no
button does.

## The panel

`Keyboard.qml`. Overlay layer, no keyboard focus, empty input region, and
`ExclusionMode.Normal` with an `exclusiveZone` of its own height - it is the
one surface that reserves space, so it does not cover what is being typed
into.

Settings: `[osk] layout`, `badges`, `badge_align`, `repeat_delay_ms`,
`repeat_rate_ms`, `labels_follow_layout`, `dictate`, `dictate_state`,
`talk_start`, `talk_stop`, `socket`, plus `[osk.keys]` and `[bindings.osk]`.
