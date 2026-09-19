# 30. The keyboard opening by itself · 🗑 Removed · S

Not having to reach for MINUS when a box that says "type here" comes up on the
couch. What was asked for was field-level: the keyboard opens **when focus
lands in a text field**.

**Field level was measured, and it is closed.** The only thing on Wayland that
says so is what an app volunteers through text-input, and reading that means
binding the seat's `zwp_input_method_v2`. A raw Wayland client was written and
run (registry → `wl_seat` + `zwp_input_method_manager_v2` →
`get_input_method`): Hyprland 0.56.2 answers with **`unavailable`** at once,
because the seat is already fcitx5's — and fcitx5 is part of Omarchy itself
(`omarchy-fcitx5.service`, for XCompose), so this is every Omarchy install.
The ways around it were eliminated one by one too: the `fcitx5-remote` state
(the same `1` with and without a text field focused), Hyprland's IPC event
stream and its Lua event list (nothing about IME or text-input), `hyprctl`
(likewise). AT-SPI was already ruled out in 28 (no D-Bus in the stdlib,
Chromium and Electron never register).

**What was built, and why it is gone.** Window level, seeing layer surfaces
too: `[osk] auto` (`never|game|always`) with `auto_match` and `auto_close`,
matching the focused window's class and title and the namespace of every layer
that was up. It was removed in use. A name is not a text field: matching an app
says nothing about whether the box in front of you wants typing, so the
keyboard came up over things that were not asking for it and stayed down for
things that were. Every guard against fighting the user — acting only on a
*change* of what is in front, never taking away a keyboard it did not open —
made it less wrong without making it right. Opening it costs one button.

Reopening this needs a signal about the *field*, not about the app. That means
either the input-method seat becoming reachable (Hyprland allowing a second
`zwp_input_method_v2`, or Omarchy dropping fcitx5) or something equivalent from
the toolkits. Until then it is closed, and the removal is the answer.
