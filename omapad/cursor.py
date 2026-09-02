"""A pointer you can find from a sofa, drawn rather than shipped.

Nothing installed on an Omarchy machine has a large round cursor, and the
couch problem is not that the arrow is the wrong shape - it is that it is
eleven pixels wide across the room. So game mode swaps the whole cursor theme
for one omapad draws itself: a ring with a dot in the middle, at whatever
size the config asks for.

Drawing it means writing the XCursor file format, which is small enough to
justify not depending on xcursorgen: a header, a table of contents, and one
chunk of premultiplied ARGB per size. Hyprland reads XCursor when no
hyprcursor theme of that name exists, which is the case for one we invented.

The theme is written once into ~/.local/share/icons and rewritten only when
the settings that shaped it change, so entering game mode costs an ioctl-free
`setcursor` and nothing else. Every cursor name points at the same ring on
purpose: from the couch an I-beam over a text field is the same unreadable
smudge as an arrow, and one shape that never changes is easier to follow than
a correct one that does.
"""

import errno
import logging
import math
import os
import struct
import tomllib

log = logging.getLogger("omapad")

# Where Omarchy keeps the colours of the theme in force. Reading the desktop's
# own file rather than being told: the shell learns the theme this way too, and
# a pointer that answers to a different palette than everything else on screen
# is the one thing on it that looks like another program.
THEME_COLORS = ("omarchy", "current", "theme", "colors.toml")

# What `auto` means for each end of the drawing. The foreground is the colour
# the theme picked to be read against its own background, which is exactly the
# job a pointer has; the background is what makes it stay readable over a
# window that is not the theme's.
AUTO = {"color": "foreground", "outline": "background"}

# How much of the theme's background the halo keeps. Solid would draw a hard
# shadow around a thin ring; this is enough to hold it against a white page.
HALO_ALPHA = 0.78

# How solid the ring's band is drawn, against a dot that is always solid. A
# ring at full strength is a hoop the pointer sits inside; a little under it
# reads as a target around the point instead of competing with what is beneath.
RING_OPACITY = 0.75

MAGIC = b"Xcur"
FILE_VERSION = 0x10000
CHUNK_IMAGE = 0xFFFD0002

# Nominal sizes written into every theme. A compositor asked for a size it does
# not find picks the nearest, so a handful of steps covers any `size` setting
# without making the file large - one 128px image is 64KB of ARGB.
SIZES = (24, 32, 48, 64, 96, 128)

# The plain pointer, which a theme has to carry whatever else it does.
POINTER_NAMES = (
    "default", "left_ptr", "arrow", "top_left_arrow", "right_ptr",
)

# Every other name a Wayland client might ask for. `shapes = "all"` points them
# all at the same ring: from the couch an I-beam over a text field is the same
# unreadable smudge as an arrow, and one shape that never changes is easier to
# follow than a correct one that does. `shapes = "pointer"` leaves them to the
# desktop's own theme for anyone who disagrees.
OTHER_NAMES = (
    "pointer", "hand", "hand1", "hand2", "pointing_hand",
    "text", "xterm", "ibeam", "vertical-text",
    "crosshair", "cross", "tcross", "cell", "color-picker",
    "grab", "grabbing", "openhand", "closedhand", "dnd-none", "dnd-move",
    "move", "fleur", "all-scroll", "size_all",
    "not-allowed", "no-drop", "forbidden", "circle", "dnd-no-drop",
    "wait", "watch", "progress", "left_ptr_watch", "half-busy",
    "help", "question_arrow", "whats_this", "context-menu",
    "copy", "alias", "dnd-copy", "dnd-link", "link",
    "n-resize", "s-resize", "e-resize", "w-resize",
    "ne-resize", "nw-resize", "se-resize", "sw-resize",
    "ew-resize", "ns-resize", "nesw-resize", "nwse-resize",
    "col-resize", "row-resize", "split_h", "split_v",
    "top_side", "bottom_side", "left_side", "right_side",
    "top_left_corner", "top_right_corner",
    "bottom_left_corner", "bottom_right_corner",
    "sb_h_double_arrow", "sb_v_double_arrow",
    "zoom-in", "zoom-out",
)

NAMES = POINTER_NAMES + OTHER_NAMES

# Coverage is sampled on a grid inside each pixel rather than computed
# analytically: a ring is two circles and the arithmetic for exact coverage is
# not worth it for an image drawn once per config change.
SUPERSAMPLE = 4


def _parse_color(text, fallback):
    """#rrggbb or #rrggbbaa -> (r, g, b, a), falling back on anything else."""
    value = str(text or "").strip().lstrip("#")
    if len(value) not in (6, 8):
        return fallback
    try:
        channels = [int(value[i:i + 2], 16) for i in range(0, len(value), 2)]
    except ValueError:
        return fallback
    if len(channels) == 3:
        channels.append(255)
    return tuple(channels)


def theme_path(root=None):
    base = root or os.environ.get("XDG_STATE_HOME") \
        or os.path.expanduser("~/.local/state")
    return os.path.join(base, *THEME_COLORS)


def theme_color(name, path=None):
    """One colour out of the desktop's theme, as `#rrggbb`, or "".

    Best-effort by design: a theme that is not there, or is not readable, or
    does not carry that key, means the caller falls back on what it shipped
    with rather than on nothing.
    """
    try:
        with open(path or theme_path(), "rb") as handle:
            data = tomllib.load(handle)
    except (OSError, ValueError):
        return ""
    value = str(data.get(name, "")).strip()
    return value if value.startswith("#") else ""


def resolve(spec, role, fallback, path=None):
    """A configured colour, with `auto` and theme key names looked up.

    `color = "auto"` is the theme's foreground and `outline = "auto"` its
    background; any other name is read from the theme as written, so
    `color = "accent"` is a pointer in the theme's accent. Anything starting
    with `#` is taken as it is, and anything the theme cannot answer falls
    back to what shipped.
    """
    text = str(spec or "").strip()
    if text.startswith("#"):
        return text
    if not text:
        return fallback
    key = AUTO.get(role, "foreground") if text == "auto" else text
    found = theme_color(key, path)
    if not found:
        return fallback
    if role == "outline" and len(found) == 7:
        # The halo is the theme's own dark, not a black one: a theme that runs
        # warm should not get a cold shadow under its pointer.
        return "%s%02x" % (found, int(HALO_ALPHA * 255))
    return found


def _coverage(cx, cy, inner, outer, dot, weight=1.0):
    """How much of the pixel at (cx, cy) the ring and the dot cover, 0..1.

    `weight` is what a sample inside the ring's band counts for, so a ring
    drawn fainter than the dot it surrounds costs one pass rather than two:
    the coverage that comes out is already the ring's own opacity.
    """
    hits = 0.0
    step = 1.0 / SUPERSAMPLE
    for sy in range(SUPERSAMPLE):
        dy = cy + (sy + 0.5) * step
        for sx in range(SUPERSAMPLE):
            dx = cx + (sx + 0.5) * step
            distance = math.hypot(dx, dy)
            if distance <= dot:
                hits += 1.0
            elif inner <= distance <= outer:
                hits += weight
    return hits / (SUPERSAMPLE * SUPERSAMPLE)


def render(size, color, outline, thickness=0.085, dot=0.05, halo=0.045,
           ring_opacity=RING_OPACITY):
    """Premultiplied ARGB bytes for one ring, and its hotspot.

    Every proportion is a fraction of the size rather than a pixel count, so
    the ring looks like itself at 24px and at 128px alike. `dot` or `halo` at
    zero leaves that part off.

    The halo is a dark band drawn under the ring on both of its edges: without
    it a white ring vanishes on a white window, and colouring the ring per
    wallpaper is a bigger promise than a pointer needs to make.

    `ring_opacity` fades the band alone. The dot stays solid: it is the pixel
    the click lands on, and the ring is only what makes it findable.
    """
    centre = size / 2.0
    band = max(1.0, size * halo) if halo > 0 else 0.0
    # The ring leaves room for its own halo. The halo is drawn *outside* the
    # ring, so an outer edge measured from the image's edge puts the halo past
    # it, and what a pointer that has been cut off at four sides looks like is
    # a ring with four flat sides. A pixel of margin past that, for the
    # antialiasing to land in.
    outer = centre - 1.0 - band
    inner = max(1.0, outer - max(1.5, size * thickness))
    dot = max(1.0, size * dot) if dot > 0 else -1.0

    ink_r, ink_g, ink_b, ink_a = color
    out_r, out_g, out_b, out_a = outline

    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            px = x - centre
            py = y - centre
            ink = _coverage(px, py, inner, outer, dot, ring_opacity)
            # The halo is the same shape grown outwards on every edge, so it
            # shows only where the ink does not already cover it.
            shade = _coverage(px, py, inner - band, outer + band, dot + band)
            a_ink = ink * (ink_a / 255.0)
            a_out = shade * (out_a / 255.0) * (1.0 - a_ink)
            alpha = a_ink + a_out
            if alpha <= 0.0:
                row += b"\0\0\0\0"
                continue
            red = ink_r * a_ink + out_r * a_out
            green = ink_g * a_ink + out_g * a_out
            blue = ink_b * a_ink + out_b * a_out
            row += struct.pack(
                "<4B",
                int(blue + 0.5), int(green + 0.5), int(red + 0.5),
                int(alpha * 255.0 + 0.5),
            )
        rows.append(bytes(row))
    return b"".join(rows), int(centre), int(centre)


def encode(images):
    """One XCursor file out of [(nominal, size, pixels, xhot, yhot), ...]."""
    header = struct.pack("<4sIII", MAGIC, 16, FILE_VERSION, len(images))
    toc_bytes = 12 * len(images)
    position = len(header) + toc_bytes
    toc = b""
    chunks = []
    for nominal, size, pixels, xhot, yhot in images:
        toc += struct.pack("<III", CHUNK_IMAGE, nominal, position)
        chunk = struct.pack(
            "<9I", 36, CHUNK_IMAGE, nominal, 1, size, size, xhot, yhot, 0
        ) + pixels
        chunks.append(chunk)
        position += len(chunk)
    return header + toc + b"".join(chunks)


def build(size, color, outline, thickness=0.085, dot=0.05, halo=0.045,
          ring_opacity=RING_OPACITY):
    """The whole cursor file for one look, at every nominal size.

    The configured size joins the standard ladder rather than replacing it: a
    compositor asked for a size that is not in the file picks the nearest and
    scales it, and the size actually asked for is the one worth having exact.
    """
    images = []
    for nominal in sorted(set(SIZES) | {int(size)}):
        if nominal < 8:
            continue
        pixels, xhot, yhot = render(nominal, color, outline, thickness, dot,
                                    halo, ring_opacity)
        images.append((nominal, nominal, pixels, xhot, yhot))
    return encode(images)


def icon_root():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "icons")


def stamp_for(size, color, outline, thickness, dot, halo, shapes, inherits,
              ring_opacity=RING_OPACITY):
    """What the theme on disk was drawn from, so a rewrite is skippable.

    The *resolved* colours, not what the config said: `auto` is a different
    pointer after the desktop's theme changes, and a stamp that could not see
    that would leave yesterday's colours on screen.
    """
    return "5 %d %s %s %.4f %.4f %.4f %.4f %s %s\n" % (
        size, color, outline, thickness, dot, halo, ring_opacity, shapes,
        inherits or "-"
    )


def install(name, size, color, outline, root=None, thickness=0.085,
            dot=0.05, halo=0.045, shapes="all", inherits="",
            ring_opacity=RING_OPACITY):
    """Write the theme, and say where it went. Returns None if it could not.

    Best-effort like everything else that leaves this process: a read-only
    home must cost a log line and the desktop's own pointer, not the daemon.
    """
    root = root or icon_root()
    color = resolve(color, "color", "#ffffff")
    outline = resolve(outline, "outline", "#000000cc")
    theme_dir = os.path.join(root, name)
    cursors_dir = os.path.join(theme_dir, "cursors")
    stamp_path = os.path.join(theme_dir, ".omapad-stamp")
    shapes = "pointer" if str(shapes).strip().lower() == "pointer" else "all"
    names = POINTER_NAMES if shapes == "pointer" else NAMES
    stamp = stamp_for(size, color, outline, thickness, dot, halo, shapes,
                      inherits, ring_opacity)
    try:
        with open(stamp_path) as handle:
            if handle.read() == stamp and os.path.exists(
                os.path.join(cursors_dir, names[0])
            ):
                return theme_dir
    except OSError:
        pass

    ink = _parse_color(color, (255, 255, 255, 255))
    edge = _parse_color(outline, (0, 0, 0, 190))
    try:
        os.makedirs(cursors_dir, exist_ok=True)
        with open(os.path.join(theme_dir, "index.theme"), "w") as handle:
            handle.write(
                "[Icon Theme]\nName=%s\nComment=omapad game-mode pointer\n"
                % name
            )
            # Only worth inheriting when this theme deliberately leaves shapes
            # out: a theme that carries every name would never reach the parent
            # anyway, and naming one there would make it look like it might.
            if shapes == "pointer" and inherits:
                handle.write("Inherits=%s\n" % inherits)
        primary = os.path.join(cursors_dir, names[0])
        with open(primary, "wb") as handle:
            handle.write(
                build(size, ink, edge, thickness, dot, halo, ring_opacity))
        # A name this theme no longer carries has to go, or a pointer-only
        # theme would keep whatever a previous "all" left behind.
        for stale in NAMES:
            if stale not in names:
                try:
                    os.unlink(os.path.join(cursors_dir, stale))
                except OSError:
                    pass
        for alias in names[1:]:
            link = os.path.join(cursors_dir, alias)
            try:
                if os.path.lexists(link):
                    os.unlink(link)
                os.symlink(names[0], link)
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    raise
        with open(stamp_path, "w") as handle:
            handle.write(stamp)
    except OSError as exc:
        log.warning("could not write the cursor theme %s: %s", name, exc)
        return None
    log.info("cursor: drew %s at %dpx in %s", name, size, cursors_dir)
    return theme_dir
