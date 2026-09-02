"""The game-mode bar: what is left on screen once Omarchy's bar is gone.

Game mode hands the pad to the game and takes the desktop bar away with it,
which leaves nothing on screen at all - including no way to remember how to get
back out. This is the replacement, and it is shaped by the one rule the desktop
bar cannot follow: every widget on Omarchy's bar opens a popup you click, and
in game mode there is no pointer to click with.

So it shows three things and none of them is a control:

- the menu, and which button opens it - a door is only worth drawing if you
  can say how to walk through it;
- the workspaces, which is the one piece of desktop state you still navigate
  by while a game is up;
- what the buttons under your thumbs do right now.

The last one is the point, and it is honest to a fault: it lists what is
*actually bound in the layer that is live*, not what the desktop would do. In
game mode that is `[bindings.game]`, which ships empty - so a pad with nothing
bound says so rather than printing a row of buttons that do nothing. The bar is
the only way to see that layer, since pressing buttons to find out is exactly
what game mode stops working.
"""

from . import guide

# The order buttons are offered in, thumbs-first: the face buttons are what a
# hint is usually about, then the shoulders, then everything else. A bar has
# room for a handful, not for a map - the guide is the map.
PREFERRED = (
    "A", "B", "X", "Y",
    "ZR", "ZL", "R", "L",
    "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
    "RSTICK", "LSTICK",
    "MINUS", "PLUS", "HOME", "CAPTURE",
)

# Beyond this the row stops reading as a hint and starts reading as a list.
MAX_ACTIONS = 3

# Which regions of the pad the row of hints is about - by kind, the way the
# guide groups them. The face buttons, and by default only them: they are the
# half of the pad that changes under you. An application profile rewrites X and
# Y, a layer rewrites all four, and what they mean where you are standing right
# now is what three slots are worth spending on.
#
# A shoulder or a trigger carries the same job wherever the scheme goes - ZR
# clicks, L and R walk the workspaces - so a slot spent on one says what the
# pad already said the first time you pressed it, in place of something you did
# not know. The two that walk the workspaces are drawn beside the workspaces
# anyway, and the one that opens the menu on the left: widening this list is
# about the row of hints and nothing else.
HINTED = ("face",)

# Gestures that mean the same thing wherever you are - confirm and go back, on
# this scheme - teach nothing by being printed. The bar has three slots and
# they are worth spending on what is different about where you are now.
#
# Matched on the action rather than on the button, deliberately: move Enter to
# another button and it stays unprinted, give A something else to do and it
# starts being printed. A list of button names would have gone stale the first
# time the scheme changed.
COMMON = ("key:ENTER", "key:ESC")

# Actions a pointer cannot fire, however clickable the badge printing them
# looks. Both of these drive the pointer itself, and the pointer is on the
# badge that was clicked: a left click would be delivered straight back to the
# thing that asked for it and ask for it again. The loop is reason enough, but
# so is the result - a click aimed at the bar reaches the bar, and was never
# going to reach whatever the badge was offering to click on.
POINTER = ("click:", "scroll:")

# A binding that walks the workspaces, so the bar can print it where the
# workspaces are rather than in the row of hints. Both shipped forms are a Lua
# dispatch naming a relative workspace - `r-1`, `e+1` - and the sign is the
# direction.
def _step_of(action):
    """-1, +1 or None for one action string."""
    if not isinstance(action, str):
        return None
    text = action.strip()
    if not text.startswith("hypr:") or "workspace" not in text:
        return None
    if "-1" in text:
        return -1
    if "+1" in text:
        return 1
    return None


def _workspace_step(spec):
    """Which way this binding walks the workspaces, and whether it is locked.

    Locked means the app in front has the plain press - a browser's tabs, a
    game - and the workspace is only reachable behind the announced hold. The
    badge still belongs beside the strip, because that is still what the button
    reaches; it just cannot be reached at a tap, and the bar has to say so or
    it is promising something a press will not do.
    """
    if isinstance(spec, dict):
        step = _step_of(spec.get("tap"))
        if step is not None:
            return step, False
        step = _step_of(spec.get("hold"))
        if step is not None:
            return step, True
        return None, False
    return _step_of(spec), False


def _tap_of(spec):
    """The action a plain press fires, which is what the bar prints."""
    if isinstance(spec, dict):
        action = spec.get("tap")
    else:
        action = spec
    return action.strip() if isinstance(action, str) else None


def _pointer_half(spec, row):
    """The action a click on this row would fire.

    The tap, or the hold where the row prints only a hold - the same choice
    the panel makes about which half to ask for.
    """
    if isinstance(spec, dict) and not row["d"] and row["h"]:
        return spec.get("hold")
    return _tap_of(spec)


def offered_to_a_pointer(spec, row):
    """Whether a click on this row may fire it at all. See POINTER."""
    action = _pointer_half(spec, row)
    if not isinstance(action, str):
        return True
    return not action.strip().startswith(POINTER)


def _spec_actions(spec):
    """Every action a binding can fire, tap and hold alike."""
    if isinstance(spec, dict):
        return [spec.get("tap"), spec.get("hold")]
    return [spec]


def mode_only(spec):
    """The `mode:` half of a binding, and nothing else.

    Game mode resolves an unbound button through the base layer but lets only
    a `mode:` action out of it, so this is what the bar is allowed to promise
    for one: HOME still says how to get back to the desktop, and the tap it
    carries on the desktop - which game mode swallows - is left off.
    """
    if isinstance(spec, str):
        return spec if spec.strip().startswith("mode:") else None
    if not isinstance(spec, dict):
        return None
    kept = {}
    for half, describes in (("tap", "desc"), ("hold", "hold_desc")):
        action = spec.get(half)
        if isinstance(action, str) and action.strip().startswith("mode:"):
            kept[half] = action
            if spec.get(describes):
                kept[describes] = spec[describes]
    return kept or None


class GameBarModel:
    """The payload the game bar draws, built from what is live right now."""

    def __init__(self, config):
        self.config = config
        # Set by the daemon when a pad connects; see guide.LAYOUTS.
        self.layout = config.badge_layout(None)
        self.workspaces = []
        self.active_workspace = None
        # {"b": badge, "ms": total} while a confirming hold is counting down.
        self.holding = None
        # Every logical button that is down right now, so the bar can light
        # the badges it draws. Logical names rather than printed badges: the
        # daemon knows buttons and the printing is the guide's question, and
        # the same list is what a pointer clicks with.
        self.pressed = []

    def set_workspaces(self, workspaces, active):
        self.workspaces = workspaces
        self.active_workspace = active

    def _badge(self, entry, side=None):
        # The badge carries the button, not the direction it moves. Arrows
        # were tried here and read worse: the side of the strip already says
        # which way, and the letter is the only thing that says what to press.
        if entry is None:
            return None
        button, locked = entry
        return {
            "b": guide.badge_of(button, self.layout),
            "k": guide.KINDS.get(button, "system"),
            # The logical name under the printed one: what the badge lights up
            # for while the button is down, and what a click on it sends back.
            "n": button,
            "locked": locked,
        }

    def menu_button(self, resolve, available):
        """The button that opens the controller menu, if one does.

        Named only when it is true: in game mode nothing is bound until
        `[bindings.game]` says so, and a menu on the bar that no button opens
        is worse than no menu at all.
        """
        for button in PREFERRED:
            if available is not None and button not in available:
                continue
            for action in _spec_actions(resolve(button)):
                if not isinstance(action, str):
                    continue
                if action.strip() in ("menu:toggle", "menu:open"):
                    return button
        return None

    def workspace_walkers(self, resolve, available):
        """The buttons that step between workspaces, if any do.

        Printed either side of the workspace strip rather than in the row of
        hints: that is where they point, and a button drawn next to what it
        moves needs no words at all.
        """
        found = {}
        for button in PREFERRED:
            if available is not None and button not in available:
                continue
            step, locked = _workspace_step(resolve(button))
            if step is None:
                continue
            side = "prev" if step < 0 else "next"
            found.setdefault(side, (button, locked))
        return found

    def actions(self, resolve, available, exclude=(), omit=COMMON):
        rows = []
        kinds = self.config.gamebar_kinds
        for button in PREFERRED:
            if len(rows) >= MAX_ACTIONS:
                break
            if button in exclude:
                continue
            if guide.KINDS.get(button, "system") not in kinds:
                continue  # not the half of the pad that changes; see HINTED
            if available is not None and button not in available:
                continue
            if _tap_of(resolve(button)) in omit:
                continue  # the same everywhere: printing it says nothing
            # The guide already turns a binding into words, and a hint that
            # disagreed with the guide would be worse than no hint. It is
            # asked for the short form of them: the guide is read from a page
            # with the pad in your lap, the bar is glanced at over a game.
            row = guide.button_row(
                button, resolve(button), self.layout, self.config.gamebar_brief
            )
            if row is not None:
                # Added here rather than in `button_row`: the guide prints
                # rows to be read, and only the bar has anything to press.
                row["n"] = button
                row["c"] = offered_to_a_pointer(resolve(button), row)
                rows.append(row)
        return rows

    def view_state(self, opened, resolve, available, mode, omit=COMMON):
        """What the shell draws. `resolve` answers with the live binding."""
        # The menu has its own place on the left, and a button printed in both
        # halves of the bar reads as two different things you can press.
        opener = self.menu_button(resolve, available)
        walkers = self.workspace_walkers(resolve, available)
        # A button already drawn somewhere on the bar is not drawn again: one
        # printed twice reads as two different things you can press.
        spoken = (opener,) + tuple(button for button, _ in walkers.values())
        actions = self.actions(resolve, available, exclude=spoken, omit=omit)
        return {
            "open": opened,
            "mode": mode,
            "menu": None if opener is None else {
                "b": guide.badge_of(opener, self.layout),
                "k": guide.KINDS.get(opener, "system"),
                "n": opener,
            },
            "wsprev": self._badge(walkers.get("prev"), "prev"),
            "wsnext": self._badge(walkers.get("next"), "next"),
            # Which badge is counting down, and over how long, so the bar can
            # walk it back to full exactly as the hold completes.
            "holding": self.holding,
            # Which buttons are down, so a badge the bar draws answers the
            # thumb on it. Sent for every button, not only the drawn ones: the
            # bar decides what it has a badge for, and a press it cannot draw
            # costs a name in a list.
            "pressed": list(self.pressed),
            # Whether a pointer may fire what a badge names. Game mode is the
            # couch environment rather than a hand-off, so there can be a mouse
            # on the desktop the bar is drawn over - and a badge saying what a
            # button does is the obvious thing to click.
            "click": self.config.gamebar_click,
            "workspaces": self.workspaces,
            "active": self.active_workspace,
            "actions": actions,
            # Which edge to sit on. "auto" means the plugin follows Omarchy's
            # own bar, which is the answer for a desktop whose bar has been
            # moved to the bottom; the daemon carries the setting rather than
            # reading the shell's config, because the shell is optional.
            "pos": self.config.gamebar_position,
            # How tall to stand. Sent rather than left to the plugin because
            # how far away the sofa is is a setting, not a shell constant.
            "h": self.config.gamebar_height,
            # How far an armed badge leans. Sent for the same reason the
            # height is: it has to be seen from the sofa, and how far away
            # that is only the user knows. How long the confirm window runs
            # is not sent beside it - the badge already has it out of
            # `holding`, and it is the sweep that spends it.
            "lean": self.config.gamebar_lean,
            # And how long it waits before it starts filling, so a tap of the
            # same button does not flash a fill nobody was asking for.
            "fill_delay_ms": self.config.gamebar_fill_delay_ms,
            # Said out loud rather than left as an empty strip: an empty row is
            # indistinguishable from a bar that has failed to load.
            "note": "" if actions else "The pad is the game's",
        }
