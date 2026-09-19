# 12. Disabling the keyboard in password fields · Constrained · L

Wayland gives no general way to ask what kind of field has focus. The only signal
is the content purpose an app volunteers through the text-input protocol, and
reading it means binding `zwp_input_method_v2` as a client.

**And that seat is taken** — measured in 30: Hyprland answers a second input
method with `unavailable`, and fcitx5 holds the first one on every Omarchy
install. So the signal is not merely partial here, it is unreachable; what
30 shipped instead is per-app, by name.

**Why it would only half work:** Quickshell exposes no input-method or text-input
type, so this cannot live in the existing plugin — it needs a separate small
Wayland client. And it only sees apps that use text-input: GTK and Qt do,
Chromium and Electron generally do not. Most password fields you meet in a
browser would go undetected, which is the worst outcome — a protection that is on
often enough to be trusted and off exactly where it matters.

**Verified:** checked against the installed Quickshell type registry.

**The premise is also worth questioning.** The on-screen keyboard doesn't add a
meaningful attack surface. It types through the same uinput device as everything
else omapad does, the daemon runs as your user rather than root, and anything
able to read that device can already read your physical keyboard. What is
genuinely different is **shoulder surfing**: an on-screen keyboard shows the
character you are about to press.

So the honest shape is a convenience, not a control — hide on detected password
fields where the signal exists, and never claim the coverage is complete. If
shoulder surfing is the real concern, suppressing the pressed-key highlight is
cheaper and works everywhere.
