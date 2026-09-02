"""Key labels taken from the compositor's own keyboard layout.

omapad types by sending evdev keycodes, so what actually lands in the focused
window is decided by the active XKB layout, not by anything here. If the
on-screen keyboard printed a fixed US QWERTY it would start lying the moment
the layout is not US: on a Turkish layout the key drawn as ';' types 'ş'.

So the labels are read back out of the same layout the compositor is using, via
`xkbcli compile-keymap`. Anything that cannot be resolved falls back to the
built-in US labels, which is exactly right on a US layout and no worse than
before anywhere else.
"""

import json
import re
import subprocess

# Keysym names for the printable ASCII that is not simply its own character.
KEYSYM_CHARS = {
    "space": " ", "exclam": "!", "quotedbl": '"', "numbersign": "#",
    "dollar": "$", "percent": "%", "ampersand": "&", "apostrophe": "'",
    "parenleft": "(", "parenright": ")", "asterisk": "*", "plus": "+",
    "comma": ",", "minus": "-", "period": ".", "slash": "/",
    "colon": ":", "semicolon": ";", "less": "<", "equal": "=",
    "greater": ">", "question": "?", "at": "@",
    "bracketleft": "[", "backslash": "\\", "bracketright": "]",
    "asciicircum": "^", "underscore": "_", "grave": "`",
    "braceleft": "{", "bar": "|", "braceright": "}", "asciitilde": "~",
    # Latin-1 and the letters layouts like tr/de/fr put on the alpha keys.
    "adiaeresis": "ä", "Adiaeresis": "Ä", "odiaeresis": "ö",
    "Odiaeresis": "Ö", "udiaeresis": "ü", "Udiaeresis": "Ü",
    "ssharp": "ß", "ccedilla": "ç", "Ccedilla": "Ç",
    "scedilla": "ş", "Scedilla": "Ş", "gbreve": "ğ", "Gbreve": "Ğ",
    "idotless": "ı", "Iabovedot": "İ", "eacute": "é", "Eacute": "É",
    "egrave": "è", "agrave": "à", "ugrave": "ù", "ntilde": "ñ",
    "aring": "å", "oslash": "ø", "ae": "æ", "AE": "Æ",
    "EuroSign": "€", "sterling": "£", "yen": "¥", "cent": "¢",
    "degree": "°", "section": "§", "mu": "µ", "periodcentered": "·",
    "nobreakspace": " ", "dead_circumflex": "^", "dead_acute": "´",
    "dead_grave": "`", "dead_diaeresis": "¨", "dead_tilde": "~",
    "dead_cedilla": "¸", "dead_caron": "ˇ", "dead_breve": "˘",
}

# XKB keycodes are evdev keycodes plus this fixed offset.
EVDEV_OFFSET = 8

_KEYCODE_RE = re.compile(r"<(\w+)>\s*=\s*(\d+)\s*;")
_KEY_BLOCK_RE = re.compile(r"key\s+<(\w+)>\s*\{(.*?)\}\s*;", re.S)
_SYMBOL_LIST_RE = re.compile(r"\[([^\]]*)\]")
# Multi-line key blocks spell the list out as `symbols[1]= [ ... ]`, and the
# `[1]` in that prefix looks exactly like a one-entry symbol list, so the
# assignment has to be matched before falling back to a bare bracket group.
_SYMBOLS_ASSIGN_RE = re.compile(r"symbols\s*\[[^\]]*\]\s*=\s*\[([^\]]*)\]")
_INDEXED_FIELD_RE = re.compile(
    r"\b(?:type|actions|virtualMods|overlay|repeat)\s*\[[^\]]*\]"
)


def _symbol_list(body):
    """The first group's symbol list from a key block body, or None."""
    match = _SYMBOLS_ASSIGN_RE.search(body)
    if match:
        return match.group(1)
    # Other indexed fields would otherwise be mistaken for the symbol list.
    match = _SYMBOL_LIST_RE.search(_INDEXED_FIELD_RE.sub("", body))
    return match.group(1) if match else None


def keysym_to_char(name):
    """Turn an XKB keysym name into the character it produces, or None."""
    name = name.strip()
    if not name or name in ("NoSymbol", "VoidSymbol"):
        return None
    if len(name) == 1:
        return name
    if name in KEYSYM_CHARS:
        return KEYSYM_CHARS[name]
    # xkb writes otherwise-unnamed symbols as U00E4 / U+00E4.
    match = re.fullmatch(r"U\+?([0-9A-Fa-f]{4,6})", name)
    if match:
        try:
            return chr(int(match.group(1), 16))
        except ValueError:
            return None
    return None


def parse_keymap(text):
    """Map evdev keycode -> (unshifted char, shifted char) from a keymap."""
    names = {}
    for name, code in _KEYCODE_RE.findall(text):
        names[name] = int(code) - EVDEV_OFFSET

    labels = {}
    for name, body in _KEY_BLOCK_RE.findall(text):
        code = names.get(name)
        if code is None:
            continue
        # Only the first group matters: it is the layout Hyprland resolves
        # against, and omapad never switches groups.
        group = _symbol_list(body)
        if group is None:
            continue
        symbols = [s.strip() for s in group.split(",")]
        plain = keysym_to_char(symbols[0]) if symbols else None
        shifted = keysym_to_char(symbols[1]) if len(symbols) > 1 else None
        if plain is None and shifted is None:
            continue
        labels[code] = (plain, shifted if shifted is not None else plain)
    return labels


def compile_labels(layout, variant="", model="", options=""):
    """Run xkbcli for a layout and return its evdev keycode -> label map."""
    command = ["xkbcli", "compile-keymap", "--layout", layout]
    if variant:
        command += ["--variant", variant]
    if model:
        command += ["--model", model]
    if options:
        command += ["--options", options]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if result.returncode != 0 or not result.stdout:
        return {}
    return parse_keymap(result.stdout)


def active_layout():
    """The layout the compositor is actually using, as (layout, variant)."""
    try:
        result = subprocess.run(
            ["hyprctl", "devices", "-j"],
            capture_output=True, text=True, timeout=3,
        )
        keyboards = json.loads(result.stdout).get("keyboards", [])
    except (OSError, ValueError, subprocess.SubprocessError):
        keyboards = []

    # Prefer the keyboard Hyprland treats as main; it is the one whose keymap
    # everything else is resolved against.
    for keyboard in sorted(keyboards, key=lambda k: not k.get("main")):
        layout = (keyboard.get("layout") or "").split(",")[0].strip()
        if layout:
            variant = (keyboard.get("variant") or "").split(",")[0].strip()
            return layout, variant

    # No compositor to ask: fall back to the console configuration.
    try:
        with open("/etc/vconsole.conf") as handle:
            settings = dict(
                line.strip().split("=", 1)
                for line in handle
                if "=" in line and not line.startswith("#")
            )
        layout = settings.get("XKBLAYOUT", "us").split(",")[0].strip('"')
        variant = settings.get("XKBVARIANT", "").split(",")[0].strip('"')
        return layout or "us", variant
    except OSError:
        return "us", ""


def labels_for_active_layout():
    layout, variant = active_layout()
    return compile_labels(layout, variant)
