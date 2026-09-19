# 26. A badge that was promising something a press would not do · ✅ Done · S

The workspace badges sit either side of the strip, which says "these walk the
workspaces". Under `[profile.browser]` or `[profile.steam]` a plain press does
not: the app has it, and the workspace is behind the announced hold. Same
badge, different behaviour - a small lie, and the thing that made the confirm
gesture undiscoverable.

Locked badges are drawn at 45% instead. **Dimmed rather than coloured**, for
three reasons worth keeping: the bar's foreground is chosen per wallpaper by
`omarchy-bar-text-color`, so a fixed hue would be illegible on some of them;
"not available at a tap" is conventionally contrast rather than colour; and it
leaves the theme's urgent colour free for the louder event.

Holding walks the dimming off over exactly `hold_ms + confirm_ms`, so the badge
is full at the moment the action fires. That makes the countdown visible - it
was a tick and a notification, both of which happen away from the thing you are
looking at - and it answers "why is this one dim?" the first time you hold it.
The daemon says a countdown has started (`holding: {b, ms}`) rather than the
bar guessing, because only the daemon knows when the press landed.

The tick got its own mark too. The gesture has two phases and the ramp only
showed one, so the badge now **arms** at `hold_ms`: thicker, and in the bar's
own urgent colour, for the confirm window. Thicker *as well as* coloured
because the theme's urgent hue is darker than the foreground on a dark bar -
hue alone read as the badge fading at the exact moment it should escalate,
which the first capture showed plainly.

**Measured** off screenshots, since opacity is not a thing to take on trust:
the badge region reads 62 at rest while locked, 66 at 1.4s into a four second
hold, and 75 unlocked.

**Found while testing:** `hyprctl dispatch focuswindow class:chromium` does
nothing on this Hyprland - dispatch goes through Lua - so the first comparison
was two screenshots of the same unfocused state. `hl.dsp.focus({ window =
'address:0x...' })` works. A reminder that a test that cannot fail is worse
than no test.
