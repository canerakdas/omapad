"""Human-readable key names to Linux input keycodes."""

KEYS = {
    "ESC": 1, "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8,
    "8": 9, "9": 10, "0": 11, "MINUS": 12, "EQUAL": 13, "BACKSPACE": 14,
    "TAB": 15, "Q": 16, "W": 17, "E": 18, "R": 19, "T": 20, "Y": 21,
    "U": 22, "I": 23, "O": 24, "P": 25, "LEFTBRACE": 26, "RIGHTBRACE": 27,
    "ENTER": 28, "LEFTCTRL": 29, "A": 30, "S": 31, "D": 32, "F": 33,
    "G": 34, "H": 35, "J": 36, "K": 37, "L": 38, "SEMICOLON": 39,
    "APOSTROPHE": 40, "GRAVE": 41, "LEFTSHIFT": 42, "BACKSLASH": 43,
    "Z": 44, "X": 45, "C": 46, "V": 47, "B": 48, "N": 49, "M": 50,
    "COMMA": 51, "DOT": 52, "SLASH": 53, "RIGHTSHIFT": 54, "KPASTERISK": 55,
    "LEFTALT": 56, "SPACE": 57, "CAPSLOCK": 58,
    "F1": 59, "F2": 60, "F3": 61, "F4": 62, "F5": 63, "F6": 64, "F7": 65,
    "F8": 66, "F9": 67, "F10": 68, "F11": 87, "F12": 88,
    "MUTE": 113, "VOLUMEDOWN": 114, "VOLUMEUP": 115,
    "RIGHTCTRL": 97, "SYSRQ": 99, "RIGHTALT": 100,
    "HOME": 102, "UP": 103, "PAGEUP": 104, "LEFT": 105, "RIGHT": 106,
    "END": 107, "DOWN": 108, "PAGEDOWN": 109, "INSERT": 110, "DELETE": 111,
    "PAUSE": 119, "LEFTMETA": 125, "RIGHTMETA": 126, "COMPOSE": 127,
    "STOPCD": 166, "AGAIN": 129, "UNDO": 131, "COPY": 133, "PASTE": 135,
    "FIND": 136, "CUT": 137, "HELP": 138, "MENU": 139,
    "NEXTSONG": 163, "PLAYPAUSE": 164, "PREVIOUSSONG": 165,
    "REFRESH": 173, "SCROLLUP": 177, "SCROLLDOWN": 178,
    "BRIGHTNESSDOWN": 224, "BRIGHTNESSUP": 225, "MICMUTE": 248,
    "BACK": 158, "FORWARD": 159,
}

ALIASES = {
    "RETURN": "ENTER", "ESCAPE": "ESC", "DEL": "DELETE", "INS": "INSERT",
    "PGUP": "PAGEUP", "PGDN": "PAGEDOWN", "PGDOWN": "PAGEDOWN",
    "SUPER": "LEFTMETA", "WIN": "LEFTMETA", "META": "LEFTMETA",
    "CMD": "LEFTMETA", "MOD": "LEFTMETA",
    "CTRL": "LEFTCTRL", "CONTROL": "LEFTCTRL",
    "SHIFT": "LEFTSHIFT", "ALT": "LEFTALT",
    "PRINT": "SYSRQ", "PRINTSCREEN": "SYSRQ", "PERIOD": "DOT",
    "XF86AUDIORAISEVOLUME": "VOLUMEUP", "XF86AUDIOLOWERVOLUME": "VOLUMEDOWN",
    "XF86AUDIOMUTE": "MUTE", "XF86AUDIOPLAY": "PLAYPAUSE",
    "XF86AUDIONEXT": "NEXTSONG", "XF86AUDIOPREV": "PREVIOUSSONG",
    "XF86MONBRIGHTNESSUP": "BRIGHTNESSUP",
    "XF86MONBRIGHTNESSDOWN": "BRIGHTNESSDOWN",
}

MODIFIER_NAMES = {
    "LEFTCTRL", "RIGHTCTRL", "LEFTSHIFT", "RIGHTSHIFT",
    "LEFTALT", "RIGHTALT", "LEFTMETA", "RIGHTMETA",
}


class KeyParseError(ValueError):
    pass


def resolve(name):
    """Resolve a single key name to its keycode."""
    key = name.strip().upper()
    key = ALIASES.get(key, key)
    if key not in KEYS:
        raise KeyParseError("unknown key name: %r" % name)
    return KEYS[key]


def parse_chord(spec):
    """Parse "SUPER+SHIFT+RETURN" into ([modifier codes], key code).

    The last segment is the key; every earlier segment must be a modifier.
    """
    parts = [part for part in spec.replace(" ", "").split("+") if part]
    if not parts:
        raise KeyParseError("empty key specification")
    mods = []
    for part in parts[:-1]:
        canonical = ALIASES.get(part.upper(), part.upper())
        if canonical not in MODIFIER_NAMES:
            raise KeyParseError("%r is not a modifier in %r" % (part, spec))
        mods.append(resolve(part))
    return mods, resolve(parts[-1])
