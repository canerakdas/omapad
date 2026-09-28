"""The stopwatch behind a `chrono` tile: three states and one pusher.

The only clock in this tree that **measures** rather than tells. `menu.py`
renders the time of day because that costs a `strftime` and cannot be wrong;
this holds something nobody can ask the machine for - when a press happened -
and so it is state, and state lives in the daemon.

**One chronograph, however many tiles draw one.** A stopwatch is a thing in the
room rather than a property of a cell: start it on the page you were on, walk
to another page, and it is the same measurement. Two of them would be two
answers to "how long has it been" with nothing on screen saying which is
which - and a second one is a thing to configure before it is a thing to use.

**One pusher, and the cycle is start, stop, reset.** That is a monopusher
chronograph, which is what a chronograph was before it had two pushers, and
it is what this pad has room for: A is the only button a tile owns. B leaves
the surface and X closes it in every layer (`docs/conventions/bindings.md`),
so the second pusher would have to be taken from one of those - a contract
exception spent on a stopwatch, on a surface where the same gesture already
has to mean *press this tile* everywhere else.

What the cycle costs is resuming: a stopped chronograph is reset by the next
press rather than restarted. That is the monopusher's own limitation on the
wrist too, and the honest half of it is that the pad says which press is
coming - `Chrono.verb()` is what the legend under the card prints, so *Reset*
is read before it is pressed rather than discovered by pressing.

**A running measurement strikes the minute.** `strike()` says, once a minute,
that the figures have rolled over another one, and the daemon answers with a
tick - the only thing a stopwatch can say to somebody who is not looking at
it, and most of what one left running while you do something else is worth.
`[chrono] rumble` is the switch, and the mark is the minute rather than a
length of time anybody set: see `MINUTE`.

Nothing here reads a clock of its own: every entry point takes `now`, which
is `time.monotonic()` in the daemon and a number in the tests. A stopwatch
that asked the wall clock what time it was would measure a machine coming back
from suspend as hours.
"""

# What it is doing, and what the next press will do to it. Three, because a
# stopwatch that has never run and one that has been stopped are not the same
# thing: the first has nothing to reset and the second has nothing else left
# to do.
IDLE = "idle"
RUNNING = "running"
STOPPED = "stopped"

# What A does next, in the interface's own voice - one word each, and each one
# is what *this* press does rather than what the thing is. It is here rather
# than in the daemon because the press and the word are one decision: a cycle
# that gained a state and left the words behind would be a legend that lies
# about the next press. `docs/conventions/writing.md` is the rule they follow.
VERBS = {IDLE: "Start", RUNNING: "Stop", STOPPED: "Reset"}

# The mark a running stopwatch strikes, in seconds. Not a setting: it is the
# unit the figures count in rather than a length of time anybody chose, and a
# strike at ninety seconds would land half way through a minute, saying
# nothing that can be read off the tile. An alarm after a length somebody set
# is a different instrument, and it would need a number on screen to set
# before it needed a motor.
MINUTE = 60.0


class Chrono(object):
    """Started, stopped, reset - and how long it has been, at any moment."""

    def __init__(self):
        # When the current run began, on the monotonic clock, or None while
        # nothing is running.
        self.at = None
        # What was measured before the current run began. It exists for a
        # resume this cycle does not have, and it is still the right shape:
        # `elapsed` reads as arithmetic rather than as a branch, and a second
        # pusher would be two lines here rather than a rewrite.
        self.gone = 0.0
        self.state = IDLE
        # How many minutes have already been struck, so a mark is answered
        # once however often the loop asks. It goes with the measurement: a
        # reset throws away the minutes struck as well as the seconds.
        self.laps = 0

    def elapsed(self, now):
        """How long it has been measuring, in seconds."""
        if self.at is None:
            return self.gone
        # Clamped because a monotonic clock is monotonic and a test's is
        # whatever it was handed: a negative elapsed would print a measurement
        # counting down, which is a fault nobody would think to look for in
        # the arithmetic.
        return self.gone + max(0.0, now - self.at)

    def strike(self, now):
        """Has another minute gone by since this was last asked?

        The one thing a stopwatch can say to a hand that is not looking at
        it: `daemon.check_chrono` turns a True into a tick, which is what a
        measurement left running while you do something else is for.

        Asked by the loop rather than fired from a timer of its own, for the
        header's reason - nothing here reads a clock - so how late the mark
        is, is whatever the loop's idle poll is, and never more than that.

        True once per minute however long it has been since the last ask: two
        marks gone by while nobody was asking is still one thing to say, and
        a motor cannot say it twice anyway.
        """
        if self.state != RUNNING:
            return False
        laps = int(self.elapsed(now) // MINUTE)
        if laps <= self.laps:
            return False
        self.laps = laps
        return True

    def verb(self):
        """What the next press does, in one word."""
        return VERBS[self.state]

    def press(self, now):
        """The pusher. Returns the state it left behind.

        Start, stop, reset, in that order and round again - see the header for
        why there is no resume in it.
        """
        if self.state == RUNNING:
            self.gone = self.elapsed(now)
            self.at = None
            self.state = STOPPED
        elif self.state == STOPPED:
            self.gone = 0.0
            self.laps = 0
            self.state = IDLE
        else:
            self.at = now
            self.state = RUNNING
        return self.state

    def view_state(self, now):
        """The two fields a `chrono` tile is drawn from.

        `el` is where the measurement had got to **when this was sent**, and
        `run` is whether it is still going - which is the whole of what the
        panel needs to count on between payloads. It is sent that way rather
        than as the figures themselves for the reason every other surface
        sends what it holds: tenths that change ten times a second cannot come
        off a wire that is written twice a second.

        Rounded to hundredths because tenths are what the tile prints and a
        float has no business carrying more precision than anybody can read
        across a wire that is re-sent twice a second.
        """
        return {"run": self.state == RUNNING,
                "el": round(self.elapsed(now), 2)}
