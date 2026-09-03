"""What a click looks like, for the quarter second after it happens.

The pointer game mode draws is a ring that never changes, and that is what
makes it findable across a room. It is also what makes it silent. A mouse
answers a click three ways - the finger feels the switch, the hand is already
on the thing that moved, and the arrow sits on what was hit - and a pad
answers none of them: the thumb is on a trigger that feels the same whatever
it did, and the pointer is a shape that looks identical before and after. A
click that landed and a click that went nowhere are the same picture.

So the daemon says where each click went and the panel draws one burst there:
a ring leaving the pointer, with the half of it on the side of the button that
was pressed drawn solid. The side rather than the colour alone, because the
two buttons have to be told apart by someone who cannot tell the two colours
apart, and because left and right are where those buttons are on the mouse
this is standing in for.

This is the one surface that is an event rather than a state, and the two
places that shows are worth knowing. There is no heartbeat: every other
surface is re-sent every `VIEW_HEARTBEAT` seconds so a restarted shell
repaints itself, but a burst that is over has nothing to repaint and
re-sending it would replay the animation twice a second forever. And there is
no `open`: what the panel watches is `n`, so a payload carrying a sequence
number it has already drawn is a duplicate rather than a second click.

Where the pointer is has to be asked of the compositor at the moment of the
press. The daemon moves the pointer in relative steps and never learns where
that put it, and a position it tracked itself would be wrong the first time a
real mouse touched the desk. That is one `cursorpos` over the Hyprland socket
per click, in the same well-under-a-millisecond class the button path already
spends on `snap`.
"""

# The buttons a burst is drawn for. Anything else a binding can click - a
# side button, a wheel tilt - fires the click and draws nothing: the drawing
# says which of the two buttons under a thumb was meant, and there is no half
# of a ring that means "the fourth one".
BUTTONS = ("left", "right", "middle")


class RippleModel:
    """The last click: where it was, which button, and how to draw it."""

    def __init__(self, config):
        self.config = config
        # Never sent as 0: the panel treats the first payload it sees as a
        # click, and a fresh shell that connects mid-session should not draw
        # one for a click that happened before it came up. `mark` increments
        # first, so the lowest sequence number ever sent is 1.
        self.seq = 0
        self.button = "left"
        self.x = 0.0
        self.y = 0.0

    def mark(self, button, position):
        """Remember one click. False when there is nothing worth drawing.

        A button no burst is drawn for, or a compositor that could not say
        where the pointer is, leaves the last one alone: a ring drawn at a
        position nobody clicked at is worse than no ring at all.
        """
        if button not in BUTTONS or position is None:
            return False
        try:
            x, y = float(position[0]), float(position[1])
        except (TypeError, ValueError, IndexError):
            return False
        self.seq += 1
        self.button = button
        self.x = x
        self.y = y
        return True

    def view_state(self):
        """The payload. `x` and `y` are the compositor's own logical pixels,
        which is the space the panel's screens are laid out in too - the panel
        subtracts its monitor's origin and no one has to agree on a scale.
        """
        return {
            "n": self.seq,
            "b": self.button,
            "x": self.x,
            "y": self.y,
            "size": self.config.ripple_size,
            "ms": self.config.ripple_duration,
            "th": self.config.ripple_thickness,
        }
