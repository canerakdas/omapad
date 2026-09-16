"""What a press sounds like, for the tenth of a second after it happens.

The pad answers a press two ways already - the thing on screen moves, and the
motor ticks - and both have a hole in them. The screen is answered by looking
at it, which is the one thing somebody walking a menu with a thumb is not
always doing; the motor is in the hands, so it cannot say anything at all
while the pad is resting on a knee, and it is off on every pad that has no
motor and every one whose owner has turned it off. A console answers the third
way: it makes a noise, and the noise is what tells a room across three metres
that a press landed.

**The vocabulary is the motor's, plus the two words the motor cannot say.**
`tick`, `edge` and `commit` are `rumble.VOCABULARY`'s own, deliberately, so
that what happened has one name and two things that can say it. The other two
are the additions, and each is a thing a motor has no way to be:

`move` is *quiet enough to repeat*. A motor that ticked on every step of a
held direction buzzes all the way down a list, which is why `[snap] rumble`
exists to turn it off - a speaker doing the same thing ticks, because a sound
decays and a vibration does not. So the selection walking a grid is the one
event that is audible and never felt.

`back` is *lower and softer than a commit*. A motor can be shorter or weaker,
which says "less happened"; it cannot fall a fourth, which says "this one went
the other way". The pair is one gesture read in two directions - the commit
bends up, the back bends down from the same note - so a room hears which of
them happened without anybody having been taught the difference. It still
ticks the hands, because a press is a press: only the speakers know which.

`texture` is the other direction and has no sound at all. It is the motor's
one held effect, and a speaker cannot hold a note under a slider for a second
and a half without becoming the loudest thing in the room.

This is an event rather than a state, and it is `ripple.py`'s shape for the
same two reasons: no heartbeat, because a sound that is over has nothing to
repaint and re-sending it would replay it twice a second forever, and no
`open`, because what the panel watches is `n` - a payload carrying a sequence
number it has already played is a duplicate rather than a second press.

It ships **off**. Every other answer this program gives is to the person
holding the pad; this one is to everybody in the room, and a desktop that
started clicking because a controller was plugged into it would be omapad
deciding something about the room rather than about the pad. One switch in the
menu, or `sound = true`, and it is on.
"""

# The words, and the order is what they cost: a move is the quietest thing
# that happens and a commit is the loudest. Each is a file of the same name
# under `assets/sounds/`, written by `assets/sounds.py`.
#
# Held effects are not here and cannot be: `rumble.VOCABULARY` has one
# (`texture`) and a speaker has no way to say it that a room would forgive.
VOICES = ("move", "back", "tick", "edge", "commit")


class SoundModel:
    """The last thing the pad said out loud, and how loudly it may say it."""

    def __init__(self, config):
        self.config = config
        # Never sent as 0: the panel treats a sequence number it has not seen
        # as something to play, and a shell that connects mid-session must
        # not announce a press that happened before it came up. `say`
        # increments first, so the lowest number ever sent is 1.
        self.seq = 0
        self.cue = VOICES[0]

    def say(self, name):
        """Remember one cue. False when there is nothing to play.

        A word that is not in the vocabulary leaves the last one alone rather
        than raising: this is called from the input path, and a sound is the
        least important thing happening at that moment.
        """
        if name not in VOICES:
            return False
        self.seq += 1
        self.cue = name
        return True

    def view_state(self):
        """The payload.

        `gain` travels with every cue rather than being sent when it changes:
        there is no heartbeat here to carry it, and a panel that had missed
        the one line saying the volume would play at the wrong one until the
        next restart.
        """
        return {
            "n": self.seq,
            "c": self.cue,
            "gain": self.config.sound_volume,
        }
