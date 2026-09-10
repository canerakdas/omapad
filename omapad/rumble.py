"""Force feedback: the pad answering a press with a tick you can feel.

Three constraints shape this. The effect is uploaded once per connection
rather than once per pulse, because an EVIOCSFF round trip inside a button
press is latency under the thumb. A tick sends its own stop rather than
trusting the one the kernel owes it. And every path is best-effort, the way
the view socket is: a pad with no motors, a node we may only read, a dongle
yanked mid-pulse - none of them is worth more than a log line.
"""

import logging
import time

log = logging.getLogger("omapad")

# How long after a tick's own length its explicit stop goes out. Buzzing and
# stopping are two packets rather than one - an Xbox pad is told to run its
# motors and runs them until something says otherwise - and the stop is the
# kernel's to send when the effect expires. It does not always arrive: the
# tick sticks on, and the next thing anybody plays is what ends it. Reported
# on a game and on a browser holding the pad, which is exactly where a second
# force-feedback client is playing effects of its own into the same device. So
# the tick ends itself and does not depend on who else is buzzing. Not a
# setting: it is a safety net on `duration_ms` rather than anything to taste,
# and it is late enough that a tick behaving normally has stopped before it
# fires.
SETTLE_MARGIN = 0.05


def _magnitude(value):
    """0..1 as the kernel wants it: an unsigned 16-bit motor level."""
    return int(max(0.0, min(1.0, float(value))) * 0xFFFF)


class Rumble:
    def __init__(self, config):
        self.enabled = config.rumble_enabled
        self.strong = _magnitude(config.rumble_strong)
        self.weak = _magnitude(config.rumble_weak)
        self.duration_ms = max(1, int(config.rumble_duration))
        self.device = None
        self.effect_id = None
        self._settle_at = None

    def configure(self, config):
        """Take the settings again, and re-upload the effect they describe.

        The effect is uploaded once per connection - an EVIOCSFF round trip
        inside a button press is latency under the thumb - so a strength
        changed while a pad is connected only reaches the motor by replacing
        the effect it was uploaded into.
        """
        device = self.device
        self.enabled = config.rumble_enabled
        self.strong = _magnitude(config.rumble_strong)
        self.weak = _magnitude(config.rumble_weak)
        self.duration_ms = max(1, int(config.rumble_duration))
        if device is not None:
            self.attach(device)

    @property
    def available(self):
        return self.effect_id is not None

    def attach(self, device):
        """Claim a freshly connected pad and upload the tick to it."""
        self.detach()
        self.device = device
        if not self.enabled:
            return
        if not device.supports_rumble():
            # Not a fault: plenty of pads have no motors, and a read-only node
            # is what you get without the udev rules.
            log.info("controller has no usable rumble motor")
            return
        try:
            self.effect_id = device.upload_rumble(
                self.strong, self.weak, self.duration_ms
            )
        except OSError as exc:
            log.warning("could not upload the rumble effect: %s", exc)

    def detach(self):
        """Give the effect slot back, if the pad is still there to take it."""
        self._settle_at = None
        if self.device is not None and self.effect_id is not None:
            try:
                self.device.erase_effect(self.effect_id)
            except OSError:
                pass
        self.device = None
        self.effect_id = None

    def pulse(self):
        if not self.available:
            return
        try:
            self.device.play_effect(self.effect_id)
        except OSError as exc:
            # The pad went away between the press and the tick; the reconnect
            # path will notice on its own.
            log.debug("rumble failed: %s", exc)
            self.effect_id = None
            self._settle_at = None
            return
        self._settle_at = (
            time.monotonic() + self.duration_ms / 1000.0 + SETTLE_MARGIN
        )

    @property
    def settling(self):
        """Is a tick still owed the stop that ends it?"""
        return self._settle_at is not None

    def settle(self, now):
        """Stop a tick whose time is up, whether or not it stopped itself.

        A stop costs one packet and is worth it: the write is what makes the
        kernel look at every effect on the device again, so a tick this one
        arrives too late for - and anybody else's that has outlived its own
        length - ends here too. Nothing to stop is not a failure; it writes
        an event and the kernel says nothing back.
        """
        if self._settle_at is None or now < self._settle_at:
            return
        self._settle_at = None
        if not self.available:
            return
        try:
            self.device.play_effect(self.effect_id, 0)
        except OSError as exc:
            log.debug("rumble stop failed: %s", exc)
            self.effect_id = None
