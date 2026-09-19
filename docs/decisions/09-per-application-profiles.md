# 09. Per-application button profiles · ✅ Done · M

A profile matched on window class, layered over the defaults, so that `B` closes
the Omarchy menu, `Paste` knows it is in a terminal, and a game gets nothing at
all. Not every app needs an entry — the point is that any app can have one.

**Shipped as `[profile.<name>]`** in the config, each with a `match` (a class
string, or a list — any hit is enough — matched as a case-insensitive
substring, so `"foot"` catches `foot` and `Alacritty` catches most natural
names) and its own `[bindings]`. A profile changes only the buttons it names;
anything else resolves as `profile → layer → base`, and the implicit surfaces
(osk, menu, guide) keep outranking whatever app is underneath, the way the
original caveat wanted. A game is just an app with a profile that binds little
(or `nop`s what it does not want) — no special "game" behaviour, because a bad
default for one app is the right one for another. A profile binding that does
not parse surfaces in `omapad check`, and the active profile is logged to
`journalctl --user -u omapad`. Where two profiles match the same class the
earlier one wins.

**How:** the daemon subscribes once to Hyprland's `.socket2.sock` and swaps the
active profile on each `activewindow` event. Two practical corrections came out
of building it:

- **Connecting streams nothing on its own.** `.socket2.sock` only pushes events
  as they happen; a fresh (or reconnected) subscription does not replay the
  current focus. So the daemon seeds once with `hyprctl activewindow -j` on
  connect as well.
- **Focus changes were already happening.** The event stream gives live focus
  changes, and reading the class off the `activewindow` event (its first field)
  is cheaper than querying on every little change.

**Verified:** live against this compositor — the event socket delivers
`activewindow>>class,title`, `hyprctl activewindow` reports the class, and a
fresh subscription seeds the profile for the window actually focused.
