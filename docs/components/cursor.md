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

`[cursor] theme` is therefore a **directory name, not a path**: `install()`
joins it onto the icon root, writes into it and unlinks from it the shapes the
theme no longer carries, so a `/` or a `..` in the name is some other theme's
directory being written to and pruned. `config.py` refuses one, which is what
lets `omapad check` name it instead of a press finding out.

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

## Going away

The ring answers where the pointer is, not whether it should be on screen at
all, and a pointer stays wherever it was left - over the menu that just opened,
the window that just moved - with no press to move it out of the way.
`Daemon.pointer_away()` is that half: a press that is not the pointer's own
work takes it off screen until something points again.

**Nothing here does the hiding.** Hyprland's `cursor:hide_on_key_press` takes
the pointer away at a keystroke and brings it back at the next movement of a
mouse; a pad is a keyboard that does not type, so the press says so itself
through `VirtualKeyboard.nudge()` - `KEY_UNKNOWN`, the keycode no layout gives
a symbol to, which is a keystroke to the compositor and nothing at all to the
window in front. Leaving both halves there is what makes this stateless: no
`hidden` flag to get wrong, nothing left behind by a daemon that dies
mid-press, and no second answer needed for the mouse on the desk - any pointer
at all brings it back, a snap included, because a warp counts as movement.

`POINTER_STAYS` in `daemon.py` is what a press has to carry to leave the
pointer where it is: click, scroll and snap, which are the pointer working,
and a key, which hides it without being asked. `check_pointer_hiding()` says
so once at startup when the compositor's own switch is off - from a sofa that
looks exactly like a setting of ours that does not work.

Settings: `[cursor] enabled`, `size`, `color`, `outline`, `thickness`, `dot`,
`halo`, `ring_opacity`, `shapes`, `theme`, `apply`, `restore_theme`,
`restore_size`; and `[pointer] hide_on_press` for the section above, which
lives there rather than here because it is true of any pointer, ring or not
(**Controller > Hide the pointer**, `pad:hide_pointer`).

## Rules

- The ring never changes, which is what makes it findable and also what makes
  it silent. What a click looks like is the other half of the same problem and
  belongs to [`ripple.md`](ripple.md), which draws its burst around whatever
  pointer is on screen.
- The daemon restores the desktop's cursor on the way out of game mode and on
  shutdown (`desktop_cursor()`, `apply_cursor(restore=True)`). A left-behind
  ring is the most visible way this can fail.
- Hiding the pointer keeps no state, and must not start keeping any. The
  compositor owns when it goes and when it comes back; anything here that
  tried to remember which it was would be a second answer to disagree with the
  one on screen.
- `SIZES` are the sizes rendered into the theme; `MAGIC`, `FILE_VERSION` and
  `CHUNK_IMAGE` are the file format and stay hardcoded.
