# Game bar - `omapad/gamebar.py` + `shell-plugin/GameBar.qml`

What is left on screen once Omarchy's bar is gone.

Game mode hides the desktop bar, which leaves nothing on screen at all -
including no way to remember how to get back out. This is the replacement, and
it is shaped by the one rule the desktop bar cannot follow: **every widget on
Omarchy's bar opens a popup you click, and in game mode there is no pointer to
click with.**

`[gamebar] enabled` and `[mode] hide_bar_in_game` are one decision defaulted
twice: both on. Off separately they give you a game mode with no bar at all,
or with two - the one you cannot reach above the one you can - so a config
that turns one off usually means to turn the other off with it.

**Two bars along one edge is also what a stale flag looks like**, and that is
why `set_gamebar()` re-runs `apply_bar()` every time ours opens. The desktop
bar follows a file (`toggles/bar-off`) that anybody may flip, and the shell's
own watch on it is documented as missing changes that land together - so the
mode switch is not the last word on it. The command names the flag rather than
toggling it, so saying it again costs a spawn and changes nothing when nothing
has changed. `Daemon.start()` says it once at startup for the same reason:
`[mode] start = "game"` has no switch to hang it on.

So it shows three things, and none of them was a control:

- the menu, and which button opens it - a door is only worth drawing if you can
  say how to walk through it;
- the workspaces, the one piece of desktop state you still navigate by;
- what the buttons under your thumbs do right now - the face buttons, which
  are the half of the pad that changes under you.

## Honest to a fault

The last one lists what is **actually bound in the layer that is live**, not
what the desktop would do. In game mode that is `[bindings.game]`, which ships
empty - so a pad with nothing bound says so ("The pad is the game's") rather
than printing a row of buttons that do nothing. The bar is the only way to see
that layer, since pressing buttons to find out is exactly what game mode stops
working.

The workspace strip answers to the same rule. It is drawn where a button walks
it and nowhere else: `view_state` sends an empty `workspaces` list when
`workspace_walkers` finds none, and the panel draws no strip for one. A
surface of ours takes the shoulders while it is up - inside the menu they pick
and go back - so under the menu, the guide or the mapping wizard the numbers
go with the badges that flanked them. A row of numbers no press steps through
is the one thing this bar promised never to print.

A surface is a layer, so opening one rewrites every hint. A press repaints the
bar on its way out of `handle_button`, but `omapad ctl menu open` and a shell
keybind have no press behind them: `Daemon.relabel_gamebar()` is what the four
`set_<surface>` calls use instead, or the bar would answer for the desktop
underneath for up to a heartbeat.

## The half that changes

The row on the right is the **face buttons and the stick clicks**
(`[gamebar] kinds`, `["face", "stick"]`). They are what an application profile
rewrites - X is the app's own verb, Y reaches for what is not on screen, and L3
and R3 are the rest of its four - and a layer rewrites all of them, so what
they mean where you are standing right now is what three slots are worth
spending on. Naming only `face` printed two of a profile's four and hid the
other two, which is why `[profile.shell]`'s copy on R3 was invisible on the one
surface whose job is to say what the pad does.

A shoulder or a trigger is the case still left out: `ZR` clicks, `L` and `R`
walk the workspaces, wherever the scheme goes. A slot spent on one repeats what
the pad told you the first time you pressed it, in place of something you did
not know yet - and neither is lost by being left out here, since the workspace
walkers are drawn beside the workspaces and the menu's opener stands on the
left. `kinds` names regions rather than buttons - `face`, `bumper`, `trigger`,
`dpad`, `stick`, `system`, the same grouping the guide reads by - so widening
it picks up every button in the region and the order stays `PREFERRED`'s.

Four buttons into `MAX_ACTIONS` slots means one falls off, and `PREFERRED` is
thumbs-first, so L3 is it. That is the right one to lose: L3 is the cheapest of
the four wherever it is spent - the click a profile reaches for once X, Y and
R3 are gone - and the guide is where the whole scheme is read. In a terminal
the row comes to *Backspace*, *Paste*, *Copy*, and `Ctrl+L` is the one left to
the guide.

## One word per hint

The bar is glanced at over the top of a game with three slots; the guide is a
page you sit and read. So it asks `guide.button_row(..., brief=True)` for the
same rows in one word - *Keyboard*, not *On-screen keyboard*. It is the same
binding read shorter and **never a different meaning**: a bar that disagreed
with the guide would be worse than a bar with no words on it. The word is the
binding's own `short` (`hold_short` for the other half), then the first word of
its `desc`, then `guide.brief_of()` for the action itself.
`[gamebar] brief = false` puts the guide's phrase back.

`COMMON` and the face-button contract meet here: the bar never prints a
gesture that means the same wherever you are, which on the shipped scheme is
exactly A and B - so an application profile that takes one of them under
`docs/conventions/bindings.md` rule 2 makes it start being printed, which is
the rule enforced by what you can see.

## It answers the pad

Every badge on it **lights up while its button is down**. The bar is the only
thing on screen in game mode, so a press it did not answer reads as a pad that
has stopped working - and on the one surface that exists to say what the
buttons do, saying which one you just pressed is the same sentence finished.
How it lights up depends on `[ui] badge_style`: a filled badge brightens, and
a stencil one inverts, the fill draining out as the punched label fills back
in - a shape already at full strength has nowhere brighter to go.
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
then shoulders, then the rest. `HINTED` is which of those regions the row is
allowed to print at all - `("face", "stick")`, the default behind
`[gamebar] kinds`: the four a profile has to spend.
`MAX_ACTIONS` (3) is where a row stops reading as a hint and starts reading as
a list. `COMMON` is what is not worth printing (`key:ENTER`, `key:ESC`). A button already drawn somewhere on the bar is never
drawn twice: one printed in two places reads as two different things you can
press.

## Payload - `gamebar.sock`

```
open, mode, menu: {b, k, n}, wsprev, wsnext, holding, pressed, click,
workspaces, active, actions: [{b, k, n, c, d, h}], pos, h, lean,
fill_delay_ms, note
```

`pos`, `h`, `lean` and `fill_delay_ms` are settings carried in
the payload rather than left to the plugin: how far away the sofa is is a
setting, and the shell cannot read the config. `holding` says which badge is
counting down and over how long, so the bar walks it back to full exactly as
the hold completes - and, past the tick, how long the sweep has to run back
out, which is why the lean needs no duration of its own. `pressed` says which
buttons are down. `click` is carried for the
same reason the geometry is. `workspaces` is **empty where no button walks
them** - that is how the daemon says to draw no strip at all, rather than the
1-5 the panel otherwise fills in.

## The panel

`GameBar.qml`, the largest file in the plugin. It borrows Omarchy's **bar**
colours (`Color.bar.*`, not the menu's) so switching modes reads as the same
bar changing its mind, and draws workspaces the way `omarchy.workspaces` does,
down to the dot the focused one becomes. `WlrLayer.Top` with
`ExclusionMode.Auto`: windows sit under it rather than behind it, and a
full-screen game covers it, which is the right outcome and needs no special
case. Our own scrims do not: the menu, the guide and the mapping wizard stand
off the strip it reserved rather than dimming the row of hints that answers
them - see [`../conventions/qml.md`](../conventions/qml.md) §7.

`restLit` / `hoverLit` / `downLit` are how lit a pressable thing is at rest,
under a pointer, and while it is down - from a thumb or from that pointer,
which are one statement about one button and so look like one. The fill carries
it rather than an outline, and a badge counting down is left alone: the sweep
is saying how much longer, and a press brightening the same fill would erase
it. `Click` is the one click surface, laid over the thing it fires so the
window's mask and what the bar answers are the same handful of items.

Settings: `[gamebar] enabled`, `position`, `height`, `confirm_lean`,
`confirm_fill_delay_ms`, `click`, `brief`, `omit`,
`kinds`, `socket`.
