"""The controller mapping wizard: which physical button is which printed one.

omapad names buttons by what is printed on the pad and picks a profile from
what the driver reports - two facts that need not agree. The Beitong KP20 is
the case that proved it: in NS mode it sends Switch Pro codes out of a shell
printed with Xbox letters, so every face button answered to its neighbour's
name and `X` produced a right click. A pad nobody has written a profile for at
all is the same problem with less to go on.

Neither is worth guessing at, so the pad is asked. The wizard walks the printed
names one at a time, writes down the code that arrives for each, and saves the
result per device identity - the KP20 alone has two, one per hardware mode.

Two rules make it drivable with nothing but the pad, which is the point of
having it on screen at all:

- a code that is already spoken for **skips** the step being asked. It is the
  only gesture available when the button being asked for does not exist on
  this pad (an Xbox pad has no Capture), and it doubles as the answer to
  pressing the same button twice.
- the last step is a confirmation drawn in the pad's *new* names, so saving is
  itself a test of what was just learned. Get it wrong and B discards it.

The daemon feeds raw codes in rather than logical names: the mapping being
fixed is the one that would otherwise do the translating.

What a step is *called* is a second question, and the same one the guide
answers: the names below are the Switch's, and a pad printed like an Xbox one
carries `View` where this says MINUS. So the screen asks in the badge of the
layout in force - `guide.badge_of` - and keeps the logical name for the file it
writes.
"""

from . import guide

# The printed names, in the order they are asked for. Face buttons first
# because they are the ones a wrong profile scrambles, then outwards to the
# ones a pad may not have at all.
STEPS = (
    "A", "B", "X", "Y",
    "L", "R", "ZL", "ZR",
    "MINUS", "PLUS", "HOME", "CAPTURE",
    "LSTICK", "RSTICK",
)

# What to call the button while asking for it. Both printings, because a pad
# whose profile is wrong is often a pad printed unlike the profile's family.
PROMPTS = {
    "A": "A", "B": "B", "X": "X", "Y": "Y",
    "L": "L, or LB", "R": "R, or RB",
    "ZL": "ZL, or LT", "ZR": "ZR, or RT",
    "MINUS": "Minus, or Back / View",
    "PLUS": "Plus, or Start / Menu",
    "HOME": "Home, or Guide - the big round one",
    "CAPTURE": "Capture, or Share",
    "LSTICK": "L3 - click the left stick",
    "RSTICK": "R3 - click the right stick",
}

# What a layout prints instead of a word. A PlayStation pad's face buttons are
# shapes, and a shape is not something to ask for out loud - "press ✕" reads as
# a crossed-out step - so those four are said in words here. Everything else is
# a printed name already.
LAYOUT_PROMPTS = {
    "playstation": {
        "A": "Cross", "B": "Circle", "X": "Square", "Y": "Triangle",
    },
}

# Which of them a pad may simply not have. Said out loud on the step itself,
# so a missing button reads as expected rather than as a wizard that hung.
OPTIONAL = frozenset(("CAPTURE", "HOME", "ZL", "ZR", "LSTICK", "RSTICK"))


class MappingModel:
    """Which button is being asked for, and what has answered so far."""

    def __init__(self, steps=None, layout=guide.DEFAULT_LAYOUT):
        self.steps = tuple(steps or STEPS)
        # Which console's printing the steps are asked in. The daemon sets it
        # from the connected profile, the same place the guide and the bar get
        # theirs; nothing here reaches for a label table of its own.
        self.layout = layout
        self.index = 0
        # name -> ("button", evdev key code) | ("axis", evdev abs code)
        self.learned = {}
        self.skipped = []
        self.confirming = False
        self.note = ""
        self.identity = ""
        self.pad_name = ""

    # -- lifecycle ---------------------------------------------------------

    def start(self, identity="", pad_name=""):
        self.index = 0
        self.learned = {}
        self.skipped = []
        self.confirming = False
        self.note = ""
        self.identity = identity
        self.pad_name = pad_name

    @property
    def step(self):
        if self.confirming or self.index >= len(self.steps):
            return None
        return self.steps[self.index]

    @property
    def done(self):
        return self.confirming

    # -- what a step is called ---------------------------------------------

    def badge(self, name):
        """What the pad in hand prints on `name`."""
        return guide.badge_of(name, self.layout)

    def prompt(self, name):
        """The step said in words, for under the badge.

        Both printings, because a pad whose profile is wrong is often a pad
        printed unlike the profile's family - which is the case this screen
        exists for.
        """
        overrides = LAYOUT_PROMPTS.get(self.layout) or {}
        return overrides.get(name, PROMPTS.get(name, ""))

    def taken(self, kind, code):
        """The name already answering to this code, if any."""
        for name, entry in self.learned.items():
            if entry == (kind, code):
                return name
        return None

    # -- learning ----------------------------------------------------------

    def learn(self, kind, code):
        """Record one press. Returns what it did, for the log and the view.

        "learned", "skipped", "ignored" - never an exception: this reads a
        controller, and a controller is allowed to send anything at all.
        """
        if self.confirming:
            return self.confirm(kind, code)
        step = self.step
        if step is None:
            return "ignored"
        already = self.taken(kind, code)
        if already is not None:
            # The escape hatch: a button that already has a name cannot be
            # meant as an answer, so it means "this pad has no such button".
            self.skipped.append(step)
            self.note = "%s skipped - that is %s" % (step, already)
            self._advance()
            return "skipped"
        self.learned[step] = (kind, code)
        self.note = ""
        self._advance()
        return "learned"

    def skip(self):
        """Skip the step being asked, from the control socket or the shell."""
        step = self.step
        if step is None:
            return False
        self.skipped.append(step)
        self.note = "%s skipped" % step
        self._advance()
        return True

    def back(self):
        """Un-ask the last step, so a misfire is not permanent."""
        if self.confirming:
            self.confirming = False
        elif self.index > 0:
            self.index -= 1
        else:
            return False
        step = self.steps[self.index]
        self.learned.pop(step, None)
        if step in self.skipped:
            self.skipped.remove(step)
        self.note = ""
        return True

    def restart(self):
        self.start(self.identity, self.pad_name)

    def _advance(self):
        self.index += 1
        if self.index >= len(self.steps):
            self.confirming = True

    # -- the confirmation --------------------------------------------------

    def confirm(self, kind, code):
        """The last step, answered in the names just learned.

        Saving with the new A is the cheapest possible test of the mapping: a
        wizard that got it wrong cannot be saved by accident, because the
        button that saves it is not where it thinks it is.
        """
        name = self.taken(kind, code)
        if name == "A":
            return "save"
        if name == "B":
            return "discard"
        if name == "X":
            self.restart()
            return "restart"
        return "ignored"

    # -- the result --------------------------------------------------------

    def buttons(self):
        """code -> name, for [pad.<id>.buttons]."""
        return {
            code: name
            for name, (kind, code) in self.learned.items()
            if kind == "button"
        }

    def triggers(self):
        """abs code -> name, for the pads that report ZL/ZR as axes."""
        return {
            code: name
            for name, (kind, code) in self.learned.items()
            if kind == "axis"
        }

    # -- the view ----------------------------------------------------------

    def rows(self):
        """Every step and where it stands, for the list on screen."""
        rows = []
        for index, name in enumerate(self.steps):
            entry = self.learned.get(name)
            if entry is not None:
                state, detail = "done", "0x%03x" % entry[1]
                if entry[0] == "axis":
                    detail = "axis 0x%02x" % entry[1]
            elif name in self.skipped:
                state, detail = "skipped", "not on this pad"
            elif index == self.index and not self.confirming:
                state, detail = "asking", ""
            else:
                state, detail = "waiting", ""
            rows.append({"n": name, "b": self.badge(name),
                         "s": state, "d": detail})
        return rows

    def view_state(self, opened):
        """The payload the shell plugin draws."""
        step = self.step
        return {
            "open": opened,
            "step": step or "",
            # The badge is what the screen shouts and the logical name is what
            # gets written down; a pad printed unlike its profile makes those
            # two different words, and the one to press is the printed one.
            "label": self.badge(step) if step else "",
            "kind": guide.KINDS.get(step, "face") if step else "face",
            "prompt": self.prompt(step) if step else "",
            "optional": bool(step and step in OPTIONAL),
            "index": min(self.index, len(self.steps)),
            "count": len(self.steps),
            "confirm": self.confirming,
            "note": self.note,
            "pad": self.pad_name,
            # The confirmation is answered in the names just learned, so it is
            # printed in them too - and on a PlayStation pad "A saves it" names
            # nothing that is on the thing in your hands.
            "keys": {
                "save": self.badge("A"),
                "discard": self.badge("B"),
                "restart": self.badge("X"),
            },
            "rows": self.rows(),
        }


def render(mappings):
    """Serialise the whole mapping file, one block per device identity.

    Written rather than merged into the user's config.toml: that file is
    hand-written and full of comments, and a program has no business rewriting
    it. Deleting this one puts every pad back on its profile.
    """
    lines = [
        "# omapad controller mappings - written by the mapping screen.",
        "#",
        "# One block per device identity, because a pad with a hardware mode",
        "# switch has more than one: the Beitong KP20 reports 057E:2009 in NS",
        "# mode and 20BC:5127 in XInput mode, and the codes differ with it.",
        "#",
        "# Delete a block to put that pad back on its shipped profile, or the",
        "# whole file to forget every mapping. [device.buttons] in config.toml",
        "# still wins over anything here.",
        "",
    ]
    for identity in sorted(mappings):
        entry = mappings[identity]
        lines.append('[pad."%s"]' % identity)
        name = entry.get("name")
        if name:
            lines.append('name = "%s"' % name.replace('"', ""))
        for table in ("buttons", "triggers"):
            codes = entry.get(table) or {}
            if not codes:
                continue
            lines.append("")
            lines.append('[pad."%s".%s]' % (identity, table))
            for code in sorted(codes):
                lines.append('0x%03x = "%s"' % (code, codes[code]))
        lines.append("")
    return "\n".join(lines)
