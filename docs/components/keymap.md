# Keymap - `omapad/keymap.py`

Human-readable key names to Linux keycodes, and the chord parser everything
that types goes through.

- `KEYS` - the name → code table.
- `ALIASES` - the second name a key is known by, in both directions people
  actually write: `SUPER`/`WIN`/`META`/`CMD`/`MOD` are all `LEFTMETA`, and the
  `XF86*` names from Hyprland configs resolve too, so a binding copied out of
  `hyprland.conf` works.
- `MODIFIER_NAMES` - which of them latch rather than type.
- `resolve(name)` - one name to a code, raising `KeyParseError`.
- `parse_chord(spec)` - `"CTRL+SHIFT+T"` to modifiers plus a code.

## Rules

- **A key that cannot be resolved raises.** `KeyParseError` from a config load
  is how `omapad check` names an unknown key instead of a binding quietly
  doing nothing.
- Adding a key means adding it to `KEYS` with its kernel code; adding a
  spelling means adding it to `ALIASES`. Never two entries in `KEYS` for one
  code.
- This table is names to codes and nothing else. What a key is *printed* with
  on the user's layout is [`xkb.md`](xkb.md); which key an on-screen cell
  types is [`osk.md`](osk.md).
