# 59. The screen that never went dark · ✅ Done · S

§4.5's last row: *after N minutes idle, dim the chrome and show art - it
protects OLEDs and looks intentional.* This program had the opposite: item 02
bound an idle inhibitor under the keyboard, the guide, the mapping screen and
the game bar, and game mode asks the desktop for `stay-awake` outright. A menu
left open on a television held the screensaver off all night.

The launcher half of that row is not ours to build - the desktop already has a
screensaver, and this is not a shell. **The fault was only that we were holding
it off with nobody at the other end of the hold.** So the hold follows the
thumb rather than the surface: a press, a D-pad step, a stick past its dead
zone, and `[idle] awake_ms` later omapad lets go and the desktop decides. The
next press takes it back.

- **`handle_button` is the one place every button, trigger and D-pad direction
  passes through**, so that is where somebody being there is recorded. A stick
  says so only past its dead zone - a pad with drift would otherwise hold the
  screen awake for ever on its own, which is the one failure this must not
  have.
- **`awake` rides on every surface's payload** through `scaled()`, because what
  it answers is true of all of them at once, and each panel binds its inhibitor
  to `opened && awake` rather than to `opened`.
- It closes item 02's open caveat from the other side as well: what holds the
  screen awake is now pad *activity* rather than a surface being open, which is
  what that caveat asked for.
