# Event loop - `omapad/daemon.py`

The one loop, and the largest module in the project (~2.5k lines). Everything
else is something it calls.

## What it owns

- The `select.poll()` loop: the pad, the real keyboards, the control socket,
  the Hyprland event socket, and a timeout.
- Which layer is live, and what a button means in it.
- Tap versus hold, chords, repeats, confirmations.
- The sticks: pointer, scroll, window resize/move, snap, focus traversal.
- Mode (desktop/game), the grab, and the handover to a game.
- Every surface's open/closed state and the pushes that keep the plugin
  painted.

## The loop

`Daemon.run()` polls; `drain_events()` reads the pad, `drain_keys()` the
keyboards, `handle_control()` the control socket, `_drain_hypr_events()` the
compositor. `tick(dt)` moves whatever is analog.

Two constants shape the timing, and both are settings' floors rather than
preferences:

| Name | Why |
|---|---|
| `IDLE_POLL_MS` | how long the loop is allowed to sleep when nothing is moving |
| `VIEW_HEARTBEAT` | how often state is re-sent so a restarted shell repaints |
| `RECONNECT_INTERVAL` | how often a missing pad is looked for again |

**Nothing in the loop may block.** Anything that shells out or waits belongs
in a thread that posts back through a queue the loop learns about by reading
one byte off a self-pipe registered with `poll()`.

`submit_command(command, done, timeout)` is that thread
([`actions.Commands`](actions.md)): it hands the command over and calls
`done(lines)` on the loop when the answer lands, so `done` may touch any state
and push any view. `drain_commands()` is the loop's end of the pipe. False
back from a submit means there is no worker - a daemon that could not make a
pipe - and the caller reads it on the loop instead, which is slower rather
than broken.

Two callers use it, both reading a command a *press* would otherwise wait for:
the keyboard page a profile lends an app (`refill_osk_app_page`) and a menu row
that lists its submenu (`menu_fill`). Both answer the press first and take the
answer when it comes: the page opens on what it held last, and the rows land
in the list the model is already drawing. Each still carries a timeout, which
is now the floor under the *thread* rather than under the pad.

**Talking to Hyprland is not shelling out.** `hypr.query()` goes down the IPC
socket in well under a millisecond; spawning `hyprctl` for the same answer
costs tens, and nothing on the loop may do it.

## Buttons

`handle_button()` → `route_button()` → `press_binding()` /
`release_binding()`, through:

- `binding_for(layer, button)` - the profile's override, then the layer, then
  fallthrough to the layer underneath. A profile overrides the base layer and
  game mode only; a held layer keeps its own bindings unless the profile names
  it (`[profile.<app>.window]`).
- `fire_chord()` / `forget_chords()` - two buttons at once, from `[chords]`.
- `set_holding()` / `check_hold_timers()` - `HOLD_MS` decides tap from hold;
  a held action that is announced leans its badge on the game bar
  (`ANNOUNCED_MS`).
- `allowed()` and `pending_confirm()` - actions from `[confirm]` need a second
  press.

`handle_button()` owns the two things that are true of *every* button event,
whatever the routing does with it: what is down (`gamebar.pressed`, which
lights the badge on the game bar) and the one push that redraws the bar
afterwards. `click_button()` is the way in for something that is not the pad -
a click on a badge, `omapad ctl press` - and it replays a tap through this
same path rather than resolving a binding of its own.

Triggers arriving as analog axes (`handle_trigger`) are thresholded with
hysteresis from `[device]`; the hat is `handle_hat()`.

## Sticks

`stick_vector()` and `scroll_vector()` apply `apply_curve()` - deadzone plus an
exponent - and then whichever role the layer gave the stick. The deadzone comes
from `config.stick_deadzone(stick)`, which is per stick rather than per role:
the slop is in the hardware, so the right one carries the same zone scrolling
the desktop as it does walking a game's controls. Roles:
`cursor`, `scroll`, `resize`, `move`, `snap`, `focus` (`STICK_ROLES`). Each has
its own emitter: `emit_cursor`, `emit_scroll` (with the ramp), `emit_window`,
`snap_cursor`, `check_focus_stick`.

## Mode, grab and handover

- `set_mode()` switches desktop/game: it hides Omarchy's bar, raises the
  surface scale, swaps the cursor theme and opens the game bar.
- `wants_grab()` / `apply_grab()` decide whether the pad is ours. The answer
  comes from `handover.wants_pad()` - does the focused window's process tree
  have the pad's node open - refreshed by `update_handover()`.
- A chord and an announced hold reach past an app holding the pad, and an open
  surface takes it back until it closes. A summon does too unless its binding
  says `reaches_past = false`, which the shipped `PLUS` and `MINUS` do.
  `allowed()` is the one place that decides; [handover](handover.md) says why.

## Surfaces

`set_osk`, `set_menu`, `set_guide`, `set_mapping`, `set_gamebar` open and
close; `push_*_view()` pushes `model.view_state(...)` through the surface's
`ViewClient`, wrapped in `scaled()` so the payload carries the scale the mode
asks for. `push_open_views()` redraws everything on screen when something
global changes. `surface_top()` and `surface_command()` route a press to
whichever surface is in front.

## Traps

- The order in `attach()` matters: the profile decides the badge layout, so
  `guide.layout` and `gamebar.layout` are set there and **nowhere else** may
  reach for a label table.
- `apply_bar()` wraps `omarchy toggle bar on|off`, which names the `bar-off`
  flag: `on` hides the bar. Read as written it does the opposite of what it
  says.
- The compositor, the plugin and the control socket are each optional. Every
  call into them is wrapped and logged; none of them may become an exception
  path.
