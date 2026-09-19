# 57. A walk that never got any faster · ✅ Done · S

[`research/console-launcher-ux.md`](../research/console-launcher-ux.md) §4.2:
*analog stick + D-pad both navigate, with stick auto-repeat and **acceleration**
on hold*, and §3's tvOS note that inertia is what makes a long row navigable at
all. Ours had the repeat and not the acceleration: a held direction stepped
every `repeat_rate_ms` from the first step to the last.

The same survey asks for edge-to-edge in six presses or a jump control, and the
keyboard's first page is fourteen keys wide. **The steps closing up is that
jump control** - the distance is the same and the journey stops being a count.

`ramped(rate, ramp, ramp_time, held)` is the whole of it, and it is linear in
*speed* rather than in the gap: ramping the gap spends most of the acceleration
in the first tenth of the walk and then crawls, and what a thumb is doing is
covering distance. It reaches both places a walk is timed - `fire_repeats`,
where a held button's repeat lives, and the two stick walkers, which count down
off the tick's own `dt` - so `[menu]`, `[osk]` and `[traverse]` each carry the
pair. A reversal starts it again: somebody pushing the other way has gone too
far, not further.

2.5 over a second ships everywhere, and 1.0 is the walk exactly as it was.
