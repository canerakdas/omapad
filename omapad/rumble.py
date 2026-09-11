"""Force feedback: the pad answering a press with something you can feel.

Four constraints shape this. Effects are uploaded once per connection rather
than once per pulse, because an EVIOCSFF round trip inside a button press is
latency under the thumb. A pulse sends its own stop rather than trusting the
one the kernel owes it. There are four effects and not one, because a pad
that answers everything with the same tick is a pad saying nothing. And every
path is best-effort, the way the view socket is: a pad with no motors, a node
we may only read, a dongle yanked mid-pulse - none of them is worth more than
a log line.
"""

import logging
import time

from .linux_input import FF_RUMBLE, FF_SINE, FF_SQUARE, FF_TRIANGLE

log = logging.getLogger("omapad")

# How long after a pulse's own length its explicit stop goes out. Buzzing and
# stopping are two packets rather than one - an Xbox pad is told to run its
# motors and runs them until something says otherwise - and the stop is the
# kernel's to send when the effect expires. It does not always arrive: the
# tick sticks on, and the next thing anybody plays is what ends it. Reported
# on a game and on a browser holding the pad, which is exactly where a second
# force-feedback client is playing effects of its own into the same device. So
# a pulse ends itself and does not depend on who else is buzzing. Not a
# setting: it is a safety net on `duration_ms` rather than anything to taste,
# and it is late enough that a tick behaving normally has stopped before it
# fires.
SETTLE_MARGIN = 0.05

# How fast the texture hums. A frequency is what makes a hum a hum rather than
# a stutter, so it is the same kind of decision as the waveform below and is
# kept out of the config for the same reason.
TEXTURE_PERIOD_MS = 120

# The four things the motor can say, and the waveform that says each. The
# waveform is not a setting: a square wave is what makes an edge feel like an
# edge, and making it configurable is offering to turn a bump into a hum.
# Strength and length are settings, because those are taste.
#
# `cycles` is the same argument one field along - two cycles is what reads as
# a bump rather than a click - so the period is computed from the length
# rather than named. `fallback` is whether plain FF_RUMBLE will do where the
# device has no periodic effects. `texture` is the one that must not: a
# continuous effect degraded onto a pulse walks into the tick that sticks on
# by another door, and a hum stuck on is not the same risk as a click stuck
# on. Where it cannot be had it is simply unavailable.
VOCABULARY = {
    "tick": {
        # Today's tick, unchanged, and everything already calling pulse()
        # lands here.
        "waveform": None, "cycles": 1, "fallback": True, "held": False,
    },
    "edge": {
        # You cannot go further.
        "waveform": FF_SQUARE, "cycles": 2, "fallback": True, "held": False,
    },
    "commit": {
        # That took.
        "waveform": FF_TRIANGLE, "cycles": 1, "fallback": True, "held": False,
    },
    "texture": {
        # It is moving, and it keeps moving until something lets go.
        "waveform": FF_SINE, "cycles": 0, "fallback": False, "held": True,
    },
}

# Upload order, which is also priority: a pad with fewer slots than we have
# effects keeps the ones nearest a plain press. Held last, because it is the
# one that ships off.
EFFECTS = ("tick", "edge", "commit", "texture")


def _magnitude(value):
    """0..1 as the kernel wants it: an unsigned 16-bit motor level."""
    return int(max(0.0, min(1.0, float(value))) * 0xFFFF)


def _amplitude(value):
    """The same, signed: a periodic effect's magnitude is an s16."""
    return int(max(0.0, min(1.0, float(value))) * 0x7FFF)


def plan(levels, supported, slots):
    """Which words this pad will take, and the waveform each is played with.

    A pure function so `omapad check` can answer the question without
    uploading anything: what it prints and what attach() does have to be one
    decision, or the report is about a different pad than the daemon has.
    A waveform of None means plain FF_RUMBLE - either the tick, or a periodic
    effect this pad cannot have falling back to one.
    """
    taken = []
    if FF_RUMBLE not in supported:
        return taken
    for name in EFFECTS:
        if len(taken) >= slots:
            break
        strength, _ = levels[name]
        if strength <= 0:
            continue
        spec = VOCABULARY[name]
        waveform = spec["waveform"]
        if waveform is not None and waveform not in supported:
            if not spec["fallback"]:
                continue
            waveform = None
        taken.append((name, waveform))
    return taken


class Rumble:
    def __init__(self, config):
        self.device = None
        self.effects = {}
        self.slots = 0
        self._settle_at = None
        self._held = set()
        self._read(config)

    def _read(self, config):
        """Take the settings, without touching the pad."""
        self.enabled = config.rumble_enabled
        self.weak = _magnitude(config.rumble_weak)
        self.duration_ms = max(1, int(config.rumble_duration))
        floor = max(0, int(config.rumble_floor))
        # The floor is on every pulse, because a pulse shorter than the packet
        # interval of the slowest supported driver can fall between two of
        # them and never reach the motor. A held effect has no length to floor.
        self.levels = {
            "tick": (config.rumble_strong, max(floor, self.duration_ms)),
            "edge": (config.rumble_edge_strength,
                     max(floor, config.rumble_edge_duration)),
            "commit": (config.rumble_commit_strength,
                       max(floor, config.rumble_commit_duration)),
            "texture": (
                config.rumble_texture_strength if config.rumble_texture
                else 0.0, 0),
        }
        self.strong = _magnitude(config.rumble_strong)

    def configure(self, config):
        """Take the settings again, and re-upload the effects they describe.

        Effects are uploaded once per connection - an EVIOCSFF round trip
        inside a button press is latency under the thumb - so a strength
        changed while a pad is connected only reaches the motor by replacing
        the effect it was uploaded into.
        """
        device = self.device
        self._read(config)
        if device is not None:
            self.attach(device)

    @property
    def available(self):
        """Is there anything uploaded to play?"""
        return bool(self.effects)

    def has(self, name):
        """Did this pad take that word? `texture` is the one that may not."""
        return name in self.effects

    def attach(self, device):
        """Claim a freshly connected pad and upload the vocabulary to it."""
        self.detach()
        self.device = device
        if not self.enabled:
            return
        try:
            supported = device.supports_effects()
        except OSError as exc:
            log.warning("could not ask the pad about force feedback: %s", exc)
            return
        if FF_RUMBLE not in supported:
            # Not a fault: plenty of pads have no motors, and a read-only node
            # is what you get without the udev rules.
            log.info("controller has no usable rumble motor")
            return
        try:
            self.slots = max(1, device.effect_slots())
        except OSError:
            # A driver that will not answer. One slot is what every rumble pad
            # has, so assume that and let anything past it fail out loud.
            self.slots = 1
        taken = plan(self.levels, supported, self.slots)
        for name, waveform in taken:
            self._upload(name, waveform)
        wanted = [n for n in EFFECTS if self.levels[n][0] > 0]
        missing = [n for n in wanted if n not in dict(taken)]
        if missing:
            # Said once per connection rather than once per press: a word this
            # pad does not have is a thing the user will notice is silent.
            log.info("the pad holds %d effects and has no %s",
                     self.slots, ", ".join(missing))

    def _upload(self, name, waveform):
        length_ms = self.levels[name][1]
        strength = self.levels[name][0]
        try:
            if waveform is None:
                # The weak level is which motor a given pad wires rather than
                # how hard this effect is, so a fallback plays on the same
                # motors the tick does.
                effect = self.device.upload_rumble(
                    _magnitude(strength), self.weak, length_ms
                )
            else:
                effect = self.device.upload_periodic(
                    waveform, _amplitude(strength),
                    self._period(name, length_ms), length_ms
                )
        except OSError as exc:
            log.warning("could not upload the %s effect: %s", name, exc)
            return
        self.effects[name] = effect

    def _period(self, name, length_ms):
        cycles = VOCABULARY[name]["cycles"]
        if not cycles:
            return TEXTURE_PERIOD_MS
        return max(1, length_ms // cycles)

    def detach(self):
        """Give the slots back, if the pad is still there to take them."""
        self._settle_at = None
        self._held.clear()
        if self.device is not None:
            for effect in self.effects.values():
                try:
                    self.device.erase_effect(effect)
                except OSError:
                    pass
        # Cleared whether or not the erase went through: a pad that has gone
        # away comes back with a fresh slot table, and an id remembered across
        # that names somebody else's effect.
        self.effects = {}
        self.slots = 0
        self.device = None

    def play(self, name="tick"):
        """Fire one of the words, if the pad took it."""
        if VOCABULARY[name]["held"]:
            raise ValueError("%s is held, not played" % name)
        effect = self.effects.get(name)
        if effect is None:
            return
        if not self._write(effect, 1):
            return
        length_ms = self.levels[name][1]
        self._settle_at = (
            time.monotonic() + length_ms / 1000.0 + SETTLE_MARGIN
        )

    def pulse(self):
        """The tick, under its old name."""
        self.play("tick")

    def start(self, name):
        """Begin a held effect. It runs until stop() says otherwise."""
        effect = self.effects.get(name)
        if effect is None or name in self._held:
            return
        if self._write(effect, 1):
            self._held.add(name)

    def stop(self, name):
        """End a held effect. Idempotent, and safe on a pad that has gone."""
        if name not in self._held:
            return
        self._held.discard(name)
        effect = self.effects.get(name)
        if effect is not None:
            self._write(effect, 0)

    def stop_held(self):
        """End everything still running. What a mode switch owes the motor."""
        for name in list(self._held):
            self.stop(name)

    def _write(self, effect, count):
        try:
            self.device.play_effect(effect, count)
        except OSError as exc:
            # The pad went away between the press and the tick; the reconnect
            # path will notice on its own.
            log.debug("rumble failed: %s", exc)
            self.effects = {}
            self._held.clear()
            self._settle_at = None
            return False
        return True

    @property
    def settling(self):
        """Is a pulse still owed the stop that ends it?"""
        return self._settle_at is not None

    def settle(self, now):
        """Stop a pulse whose time is up, whether or not it stopped itself.

        A stop costs one packet and is worth it: the write is what makes the
        kernel look at every effect on the device again, so a tick this one
        arrives too late for - and anybody else's that has outlived its own
        length - ends here too. Nothing to stop is not a failure; it writes
        an event and the kernel says nothing back. A held effect has no time
        to be up, so nothing here can cut one short.
        """
        if self._settle_at is None or now < self._settle_at:
            return
        self._settle_at = None
        effect = self.effects.get("tick")
        if effect is None:
            return
        self._write(effect, 0)
