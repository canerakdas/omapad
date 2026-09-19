# 13. Caps Lock that works, and shows · ✅ Done · S

The `Caps` key did nothing, and the reason was not in omapad: Omarchy's own
layout ships `compose:caps,shift:both_capslock_cancel`
(`/usr/share/omarchy/default/hypr/input.lua`), which turns the Caps Lock key
into Compose. `KEY_CAPSLOCK` toggles nothing at all on a stock Omarchy. So the
shipped default sends what that layout *does* answer to — **both shifts
together** — through item 14's override table rather than hard-coded, so a
layout that was never remapped puts it back in one line. **Verified** against
`hyprctl devices`: off → on → off.

**Showing it needed a state omapad does not own**, and the obvious route is
closed:

- Declaring `EV_LED` on the virtual keyboard gets nothing back — no event on
  the uinput fd, and `EVIOCGLED` stays zero. Hyprland does not push LED state
  to it. **Verified.**
- But caps lock is held **per keyboard device**: `hyprctl devices` shows this
  device's caps `true` while the physical keyboard's stays `false`. omapad
  owns the device its keys are typed from and is the only thing that ever
  toggles that device's caps — so following its own presses is not an
  approximation, it is the state that applies to what this keyboard types.
  **Verified.**

What that buys: letters print uppercase while caps is on, digits and
punctuation do not move, Shift over Caps goes back down, the labels still come
from the live XKB layout (`tr` prints `I` on the `ı` key), and the `Caps` key
stays lit the way a latch does. Nothing changes about what is *typed* —
omapad sends keycodes and the compositor applies caps itself. It survives the
keyboard closing, the way a real Caps Lock does.

`osk:caps` is the action, so L3 and the on-screen key take one path: the key
itself decides what gets sent, and both update the printed labels.
