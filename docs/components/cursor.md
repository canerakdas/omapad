# Cursor - `omapad/cursor.py`

A pointer you can find from a sofa, drawn rather than shipped.

Nothing installed on an Omarchy machine has a large round cursor, and the couch
problem is not that the arrow is the wrong shape - it is that it is eleven
pixels wide across the room. So game mode swaps the whole cursor theme for one
omapad draws itself: a ring with a dot in the middle, at whatever size the
config asks for.

## Why it writes XCursor by hand

The format is a header, a table of contents and one chunk of premultiplied
ARGB per size - small enough to justify not depending on `xcursorgen`.
Hyprland reads XCursor when no hyprcursor theme of that name exists, which is
the case for one we invented.

The theme is written into `~/.local/share/icons` once and rewritten only when
the settings that shaped it change (`stamp_for()` is the fingerprint), so
entering game mode costs a `setcursor` and nothing else.

**Every cursor name points at the same ring on purpose.** From the couch an
I-beam over a text field is the same unreadable smudge as an arrow, and one
shape that never changes is easier to follow than a correct one that does.
`POINTER_NAMES` and `OTHER_NAMES` are the names that get the same drawing.

## Colour

`auto` means the theme's own: `theme_color()` reads Omarchy's
`current/theme/colors.toml` - the same file the shell learns the theme from,
because a pointer answering to a different palette than everything else on
screen is the one thing on it that looks like another program. The foreground
is what the theme picked to be read against its own background, which is
exactly a pointer's job; the background is what keeps it readable over a window
that is not the theme's.

## Surface

`render(size, ...)` draws one image (`_coverage` antialiases by
`SUPERSAMPLE`), `encode(images)` writes the file, `build()` does both,
`install(name, size, color, outline, ...)` puts the theme where Hyprland will
find it, `resolve(spec, role, fallback)` turns a config value into a colour.

Settings: `[cursor] enabled`, `size`, `color`, `outline`, `thickness`, `dot`,
`halo`, `ring_opacity`, `shapes`, `theme`, `apply`, `restore_theme`,
`restore_size`.

## Rules

- The ring never changes, which is what makes it findable and also what makes
  it silent. What a click looks like is the other half of the same problem and
  belongs to [`ripple.md`](ripple.md), which draws its burst around whatever
  pointer is on screen.
- The daemon restores the desktop's cursor on the way out of game mode and on
  shutdown (`desktop_cursor()`, `apply_cursor(restore=True)`). A left-behind
  ring is the most visible way this can fail.
- `SIZES` are the sizes rendered into the theme; `MAGIC`, `FILE_VERSION` and
  `CHUNK_IMAGE` are the file format and stay hardcoded.
