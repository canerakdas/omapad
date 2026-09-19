# 03. Controller buttons inside the keyboard · ✅ Done · S

Pure configuration in `[bindings.osk]`. Done:

| Button | Today | Now |
|---|---|---|
| `B` | Backspace | Close the keyboard |
| `X` | Space | Backspace |
| `Y` | Shift latch | Space |
| `L3` | Left click | Caps Lock |
| `LT` | — | Shift, held |

**The `LT` row is built, and it needed two mechanisms.** Both triggers now mean
something else while the keyboard is up:

| Trigger | While the keyboard is open |
|---|---|
| `ZL` / `LT` | **Shift, held** — down for as long as the finger is |
| `ZR` / `RT` | **`osk:submit`** — Enter, then the keyboard goes away |

- **A held modifier, not a latch.** `osk:hold:<mod>` sets the modifier on press
  and clears it on release, and `clear_latches()` now spares whatever a finger
  is holding — so `ZL` plus `q w e` types `QWE`, while the on-screen `Shift`
  still falls away after one key. The two write to the same `mods` state and do
  not fight. A hold is dropped when the keyboard closes, because the trigger's
  release is not routed to the keyboard once it is down.
- **A surface binding now outranks a layer trigger.** `ZL` holds the window
  layer everywhere else, and a layer trigger never fired its own binding. The
  keyboard and the menu are implicit layers, so they had no way to shadow one;
  `surface_override()` gives them that, checked in the same order the surfaces
  outrank each other. The cost is deliberate: **window ops are unreachable
  while the keyboard is open** — a button cannot mean two things, and typing is
  what the keyboard is for.
- `ZR` is left click at the base layer, and clicking into another field is
  worth keeping while typing, so left click moved to the **right stick click** —
  the thing already aiming the cursor. Not `CAPTURE`, which looks free but
  exists only on the `nintendo_pro` profile: a click parked there would do
  nothing in XInput mode.
