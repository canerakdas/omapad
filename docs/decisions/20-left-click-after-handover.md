# 20. Left click in a browser the pad had been handed to · ✅ Done · S

Reported as a bug — *left click doesn't work in the browser in gaming mode* —
and it was not one: `mode=game` had been on since the last mode switch, and in
game mode nothing but a `mode:` action ran. Right, whenever the game really is
the whole screen. It is wrong for the case that keeps coming up: a cloud
session in a browser, an emulator's own menu, a launcher. There the pad has to
reach the game *and* the page around it, and the desktop mode that could click
is the one that stops the page from seeing the pad at all.

`[bindings.game]` is the answer, and it is empty by default: game mode still
means the game gets the pad, and every button named here is one it stops
getting. Three things fall out of it being a layer rather than a special case.
It is **flat** — no layer opens inside it and no surface shows — so ZL is an
ordinary bindable button there rather than the window trigger. It **falls back
to base for the way out only**: a base binding is resolved but tagged with
where it came from, and `allowed()` lets a `mode:` action out of it and nothing
else, so HOME's hold and the chord keep working without the layer repeating
them — and a button the layer does name takes the base one's place, holds
included. And the guide grows a page for it the moment it is non-empty, which
is the one thing about game mode you cannot work out by pressing buttons.

The sticks needed their own answer. A click with a frozen cursor is worth
little, and the tick was gated on `mode == "desktop"`; it now follows the
stick's role instead, with `[mode] game_left_stick` / `game_right_stick`
defaulting to `none`. Off is still off, and the loop still sleeps: `needs_tick`
asks whether any stick has a role before it asks whether one is deflected.

**Still open.** Nothing says which buttons a game already uses, so a config
that names too many is a config that eats the game's own controls; the guide
page is the only warning. Suspicion, not measurement: the sticks are the part
worth being careful with, since a game reading the pad directly sees them too.
