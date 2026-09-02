# Game bar - `omapad/gamebar.py` + `shell-plugin/GameBar.qml`

What is left on screen once Omarchy's bar is gone.

Game mode hides the desktop bar, which leaves nothing on screen at all -
including no way to remember how to get back out. This is the replacement, and
it is shaped by the one rule the desktop bar cannot follow: **every widget on
Omarchy's bar opens a popup you click, and in game mode there is no pointer to
click with.**

So it shows three things, and none of them was a control:

- the menu, and which button opens it - a door is only worth drawing if you can
  say how to walk through it;
- the workspaces, the one piece of desktop state you still navigate by;
- what the buttons under your thumbs do right now.

## Honest to a fault

The last one lists what is **actually bound in the layer that is live**, not
what the desktop would do. In game mode that is `[bindings.game]`, which ships
empty - so a pad with nothing bound says so ("The pad is the game's") rather
than printing a row of buttons that do nothing. The bar is the only way to see
that layer, since pressing buttons to find out is exactly what game mode stops
working.

## It answers the pad

Every badge on it **lights up while its button is down**. The bar is the only
thing on screen in game mode, so a press it did not answer reads as a pad that
has stopped working - and on the one surface that exists to say what the
buttons do, saying which one you just pressed is the same sentence finished.
`pressed` carries every button that is down, in logical names; which of them
the bar has a badge for is the panel's question.

## And a pointer, where there is one

Game mode is the couch environment rather than a hand-off, so the desktop is
still under this bar and the mouse may still be on the desk. Clicking a badge
fires exactly the binding the press would - `omapad ctl press <BUTTON>`, so
the daemon resolves it through the same layer, profile and tap/hold path, and
the panel never learns what a button means. A hint that is only a hold is
clicked as a hold, since that is what it prints.

One thing is refused: a binding that **drives the pointer itself** (`POINTER` -
`click:`, `scroll:`). It would click wherever the pointer is, which is the badge
that was clicked, so the answer would land straight back on the badge and ask
for another - and a click aimed at the bar reaches the bar, never what the badge
was offering to click on. `actions()` marks those rows `c: false`; they are
still drawn and still light up under their own button.

The window's input mask is the whole strip while `[gamebar] click` is on, and
empty when it is off - a click then goes straight through, the way it did
before the bar was clickable. The whole strip rather than the badges alone
because a mask is one region here: nested `Region`s do not union in this
Quickshell, and the bar reserves its own strip anyway, so what a click on the
empty half of it would otherwise have reached is the wallpaper.

## `GameBarModel`

`view_state(opened, resolve, available, mode, omit)` - `resolve(button)`
answers with the live binding, so the model never reaches into the config for
it. `menu_button()` names the opener **only when one is really bound**;
`workspace_walkers()` finds the buttons that step workspaces and prints them
either side of the strip, where they point; `actions()` picks the rest.

Every badge carries `n`, the logical button under the printed label: what
`pressed` is matched against and what a click is sent back as. `button_row()`
does not add it - the guide prints rows to be read, and only the bar has
anything to press.

`PREFERRED` is the order buttons are offered in, thumbs-first: face buttons,
then shoulders, then the rest. `MAX_ACTIONS` (3) is where a row stops reading
as a hint and starts reading as a list. `COMMON` is what is not worth printing
(`key:ENTER`, `key:ESC`). A button already drawn somewhere on the bar is never
drawn twice: one printed in two places reads as two different things you can
press.

## Payload - `gamebar.sock`

```
open, mode, menu: {b, k, n}, wsprev, wsnext, holding, pressed, click,
workspaces, active, actions: [{b, k, n, c, d, h}], pos, h, tremble,
tremble_ms, fill_delay_ms, note
```

`pos`, `h`, `tremble`, `tremble_ms` and `fill_delay_ms` are settings carried in
the payload rather than left to the plugin: how far away the sofa is is a
setting, and the shell cannot read the config. `holding` says which badge is
counting down and over how long, so the bar walks it back to full exactly as
the hold completes, and `pressed` which are down. `click` is carried for the
same reason the geometry is.

## The panel

`GameBar.qml`, the largest file in the plugin. It borrows Omarchy's **bar**
colours (`Color.bar.*`, not the menu's) so switching modes reads as the same
bar changing its mind, and draws workspaces the way `omarchy.workspaces` does,
down to the dot the focused one becomes. `WlrLayer.Top` with
`ExclusionMode.Auto`: windows sit under it rather than behind it, and a
full-screen game covers it, which is the right outcome and needs no special
case.

`restLit` / `hoverLit` / `downLit` are how lit a pressable thing is at rest,
under a pointer, and while it is down - from a thumb or from that pointer,
which are one statement about one button and so look like one. The fill carries
it rather than an outline, and a badge counting down is left alone: the sweep
is saying how much longer, and a press brightening the same fill would erase
it. `Click` is the one click surface, laid over the thing it fires so the
window's mask and what the bar answers are the same handful of items.

Settings: `[gamebar] enabled`, `position`, `height`, `confirm_tremble`,
`confirm_tremble_ms`, `confirm_fill_delay_ms`, `click`, `omit`, `socket`.
