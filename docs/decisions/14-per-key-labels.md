# 14. Per-key labels and actions · ✅ Done · S

`[osk.keys]` overrides what a keyboard key **shows** or **does**, keyed by the
action it has by default — the one stable name a key has, since nobody wrote
down a row and a column:

```toml
[osk.keys]
BACKSPACE = ""                  # a bare string is the label
close     = { label = "" }      # the key that puts the keyboard away
CAPSLOCK  = { action = "CAPSLOCK" }   # undo the shipped default
```

The shell draws with Omarchy's Nerd Font, so its glyphs work as labels. A key
that appears on more than one page is overridden on all of them — the only
answer that does not surprise. A user's label outranks the XKB lookup, which
would otherwise print the layout's character over it. Overrides apply to a copy
of the shipped layout, so they cannot leak into it, and `omapad check`
refuses an action that does not parse.

**This is item 11 arriving from the other end.** 11 wants to *see* the whole
map; this lets one key of it be changed without touching Python. The two do not
conflict — a read-only view of the map is still most of 11's value.
