# 02. The screensaver interrupting the keyboard · ✅ Done · S

This isn't a stacking problem. The keyboard already sits on the overlay layer,
above every ordinary window, and the screensaver is an ordinary window. What
actually happens is that **the idle timer runs while you use the controller**:
navigating the keyboard moves a selection over a socket and produces no Wayland
input at all, so as far as the compositor is concerned the session was
untouched.

**Done:** `Keyboard.qml` now binds a Quickshell `IdleInhibitor` (`Quickshell.Wayland`)
to the panel window's `opened` property. Omarchy's idle service runs its monitor
with `respectInhibitors: true`, so the screensaver is held off while typing.

**Worth extending past the keyboard (not done):** any pad activity in desktop
mode should hold the inhibitor with a short trailing timeout, otherwise reading
a page with the right stick still counts as idle.
