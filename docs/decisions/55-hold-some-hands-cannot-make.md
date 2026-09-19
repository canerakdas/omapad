# 55. A hold some hands cannot make · ✅ Done · S

From the September 2026 console-launcher survey in
[`research/console-launcher-ux.md`](../research/console-launcher-ux.md), §4.10:
*button remapping system-wide; hold-to-press → toggle alternative for
hold-confirm actions.* Everything else in that paragraph this project already
had - remapping is a screen, reduce-motion is a slider, no menu is on a timer -
and this one it did not: **every hold on the pad was a hold, at a length
written into the binding.** Two seconds of keeping a shoulder down is a gesture
some hands cannot make at all, and others make by accident.

The literal XAG answer - a press that latches the button down - does not fit
here, and finding out why is most of what this item is. Every announced hold in
the shipped tree is **half of a tap/hold pair**: `L` walks a browser tab and,
held, walks a workspace. A gesture that replaced the hold with a press has to
take the press from somewhere, and the only place to take it from is the tap.
So the answer is two numbers rather than a new gesture, and each of them
removes a different part of the difficulty:

| `[confirm]` | What it takes away |
|---|---|
| `scale` | the length. One multiplier over **every** wait on the pad - the announced pair, a binding's own `hold_ms`, the half-second a plain hold takes - bounded to 0.5–2.0, because under a half a tap and a hold stop being different gestures and over a double nobody reaches the end of one |
| `slack_ms` | the *continuity*. How long the finger may come off a hold that has **already announced itself**. Set it to `confirm_ms` and letting go after the tick stops cancelling at all: hold until the pad ticks, take the thumb off, and it still fires |

- **The scale is applied in `Binding`, not where the timers are read.** The
  game bar fills a badge over `hold_ms` and empties it over `confirm_ms`; a
  scale that reached the loop and not the payload would be a promise counting
  down over a bar that had already finished. The cost is a cache to clear -
  `apply_setting` drops `bindings` and `page_keys`.
- **The slack starts at the announcement and never before it.** Before it,
  letting go is how a tap is made, and a browser tab that waited out a slack
  nobody turned on for tabs would be the bill for a setting about something
  else.
- `hold_scale` is on the pad as `Controller ▸ Hold time`, which is the whole
  point: the person who cannot make the gesture is the last person who should
  have to find a text editor to say so.

Both ship neutral - `scale = 1.0`, `slack_ms = 0` - so the gesture is exactly
what it was until somebody says otherwise.
