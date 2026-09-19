# 33. The game behind Big Picture, and the menu rows that died with it · ✅ Done · S

Reported from the sofa: *launch a game from Steam Big Picture and Steam stays in
front of it; I have to close Steam, and I cannot close Steam with the
controller either.* Two separate faults, and the second one turned out to be
ours.

**The stacking is Hyprland's, and no dispatcher fixes it.** Omarchy floats every
Steam window and the rule matches the class exactly, so Big Picture (class
`steam`) floats while a game launched from it (class `steam_app_<id>`) tiles.
A floating window is **always** drawn above a tiled one - a layering rule, not a
z-order - which is why the obvious answers do nothing.

**Measured**, with two terminals standing in for the pair (`--app-id=steam` and
`--app-id=steam_app_888`, so the real rules applied to them):

| Dispatcher | What the screenshot showed |
|---|---|
| `hl.dsp.window.cycle_next()` | focus moved to the "game" - its border lit - and it stayed covered |
| `hl.dsp.window.bring_to_top()` | no change at all; a tiled window cannot be raised over a floating one |
| `hl.dsp.window.fullscreen({ mode = 'fullscreen' })` | the "game" covered the screen, Big Picture gone |

So the fix is a window rule, and it belongs in the user's Hyprland config rather
than in this repo - the README says which line, next to the hand-off it belongs
to. It is the same answer Omarchy already gives RetroArch and Moonlight:
`o.window("steam_app_.*", { fullscreen = true, idle_inhibit = "fullscreen" })`.

**The pad-side half is a `Windows` row in the menu** - fullscreen, next window,
float/tile, close - because the window layer (`ZL`) already has all of it and
none of it reaches past an app holding the pad. A summon does, and the menu is
the summon. `Fullscreen` is first in the submenu because it is the row that
actually clears the case above.

**And that is where the real bug was.** A picked row fires *after* the menu is
put away - deliberately, so what it opens does not come up behind a scrim - and
`allowed()` was reading `menu_open` at that moment, which is now False. With the
pad handed to a game, every row that was not itself a summon was **silently
dead**: `Terminal`, `Ask about this screen`, the whole Audio and Screen
submenus. Only `Keyboard`, `Bindings` and `Game mode` worked, because those are
summons and summons are allowed by kind. In other words the menu was at its most
useless exactly where it is the only thing you have.

`allowed()` now takes the surface layer a row was tagged with as its own answer:
the button that chose the row was ours, on a surface the pad was driving, and
closing the surface first is an implementation detail of how it is drawn.
`fire_once(action, "menu")` had been passing that tag since the menu was
written; nothing read it.
