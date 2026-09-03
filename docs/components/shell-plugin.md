# Shell plugin - `shell-plugin/`

An Omarchy shell plugin (Quickshell, QML) that draws six surfaces and one bar
widget. What is symlinked into
`~/.config/omarchy/plugins/canerakdas.omapad` is the **checkout root**, not
this folder - `manifest.json` lives at the root so `omarchy plugin add` installs
the daemon with it - so this checkout is the live source.

Write it by [`../conventions/qml.md`](../conventions/qml.md); this document is
what is in it.

## Entry points - `../manifest.json`

Paths are relative to the manifest, which is one level up, so each carries the
`shell-plugin/` prefix.

| Kind | File | What |
|---|---|---|
| `panel` | `shell-plugin/Surfaces.qml` | every summonable surface |
| `bar-widget` | `PadStatus.qml` | "is the pad mine?" in the Omarchy bar |

`keepLoaded: true`, so the panels are alive to receive a socket line before
anybody asks for them.

## `Surfaces.qml`

A plugin gets one panel entry point and omapad draws six independent
surfaces, so they are mounted here - one hot-reloading plugin directory
instead of six.

The shell's summon/hide/toggle contract lands on `open()`, `close()` and
`opened`, so `omarchy-shell shell summon canerakdas.omapad` and an
Omarchy keybind reach the same surfaces the pad does. **Neither function opens
a panel itself**: it shells out to `omapad ctl <verb> open`, exactly the way
a terminal would, and the answer comes back over the surface's socket.
Flipping `opened` here would draw a surface the daemon does not know it is
showing, and its next heartbeat would take it away again.

`summonable` maps a payload name to a surface; `surfaceNames` accepts both the
control verb and the obvious word for it (`keyboard` → `osk`). A summon with
no payload means the menu - the door the pad's own button opens. The game bar
is deliberately not summonable: it follows game mode, and
`omapad ctl mode` is its door.
`Ripple.qml` is not summonable either, and has no `opened`: it answers a click
rather than a button.

## The surfaces

| File | Component |
|---|---|
| `Keyboard.qml` | [`osk.md`](osk.md) |
| `Menu.qml` | [`menu.md`](menu.md) |
| `Guide.qml` | [`guide.md`](guide.md) |
| `Mapping.qml` | [`mapping.md`](mapping.md) |
| `GameBar.qml` | [`gamebar.md`](gamebar.md) |
| `Ripple.qml` | [`ripple.md`](ripple.md) |
| `PadStatus.qml` | [`status.md`](status.md) |

## Shared pieces

- **`Metrics.qml`** - the shell's measurements at omapad's own scale. Every
  surface here is read from twice the distance an Omarchy menu is, and the
  shell has one scale for the whole session, so this multiplies it per surface
  from the number the daemon stamps on every payload (`[ui] scale`,
  `game_scale`). A multiplier rather than a replacement, so a roomy theme
  stays roomy. `Style.cornerRadius` and `Style.gapsOut` are **not** scaled:
  they are the compositor's own geometry, and a surface rounded harder than
  the windows beside it just looks wrong.

  `metrics.badge(px)` is the other exception: a badge box has to be whole
  pixels on **both** sides, because BadgeArt scales the drawing by one factor
  taken from the width. Every shape is 32 units tall but a system button is 40
  by 48, so the height is snapped up to a multiple of five - the smallest step
  that keeps `unit * w / h` whole for all of them. Off the grid the pill's rim
  lands mid-pixel and is painted grey instead of drawn. Size a badge with this
  and nothing else.
- **`BadgeArt.qml`** - paints one controller button in given colours. Decides
  nothing: the caller picks the entry, the colours and the stroke weight, and
  this scales the drawing. Set the width; the height follows the drawing's
  aspect, because a squashed button stops reading as one - and the box the
  caller gives has to carry that aspect exactly, which is what
  `Metrics.badge` is for. `strokeWidth` is set
  once and not animated - the mapping screen is the only surface that outlines
  a badge at all, and the countdown that used to thicken an outline is drawn
  by the game bar's fill sweep now.

  Two things that look like savings here were measured and are not:

  - **Building the `Shape` behind a `Loader`** so a badge with no drawing
    skips it. The keyboard carries one `BadgeArt` per key and only about a
    quarter of them draw anything, so this looked free. It cost 2.30 → 2.40 ms
    of shell CPU per keystroke and about 3 MB: a `Loader` and its `Component`
    per badge is more than the empty `Shape` they were meant to save.
  - **Making `ButtonArt.qml` a `pragma Singleton`** so the four surfaces share
    one table instead of four. The table really is about 180 kB an instance,
    so this is roughly 540 kB on the floor - but the singleton does not
    register from a plugin directory. The name resolves and the properties do
    not: `TypeError: Property 'find' of object ButtonArt is not a function`,
    and all four surfaces stop drawing badges. Quickshell's own `Commons/`
    singletons work because they are part of the shell, not a plugin.
- **`ButtonArt.qml`** - **GENERATED** by `assets/generate.py`. Every drawn
  button as path data, plus the `FontLoader` for Fira Code. Do not edit; see
  [`assets.md`](assets.md).
- **`fonts/`** - Fira Code Medium and its OFL licence. Here rather than beside
  the shapes because `omarchy-plugin-validate` rejects a symlink inside a
  plugin folder, so the one copy has to be the one the plugin can reach.

## Reloading

```bash
omarchy-shell shell rescanPlugins   # after editing an existing .qml
omarchy-restart-shell               # after ADDING a .qml, and when an edit does not take
qs -p /usr/share/omarchy/shell log  # the only place the real error appears
```

Qt caches the directory listing per process, so a brand-new file fails to load
with a misleading `File name case mismatch` and the panel silently stays down.
Panel entry points have been seen to resist `rescanPlugins` even on an edit;
the bar widget never does.
