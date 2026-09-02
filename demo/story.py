"""The storyboard: what the take shows, in the order it shows it.

Every press here goes in through /dev/uinput, so the daemon reads it the way it
reads a thumb - taps, holds, chords and layer triggers all decided by the same
code that decides them on hardware. Nothing drives a surface through the
control socket, because a video of the control socket is not a video of the
plugin.

Captions name buttons **logically** - "ZL", "MINUS" - and are printed through
`guide.badge_of`, the one place allowed to answer what a badge prints. So the
caption and the badge on screen cannot disagree, and switching `layout` in
`config.toml` re-letters the whole video without a line changing here.

Each beat writes a cue line - a monotonic timestamp, the buttons, what they do
- and `captions.py` burns those in afterwards.
"""

import json
import os
import subprocess
import sys
import time

import pad as pad_module

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from omapad import config as config_module, guide, linux_input as li

CONFIG = os.path.join(HERE, "config.toml")
CUES = os.path.join(HERE, "cues.jsonl")

# How long to wait for the daemon to come up on the demo pad before giving up.
# Generous: the first run after a reboot pays for udev as well.
DAEMON_TIMEOUT = 15.0


def badge_layout():
    """Which console's printing this take will be showing.

    Resolved the way the daemon resolves it in `attach()` - from the profile
    the connected pad detects into - so `layout = "auto"` works here too.
    """
    config = config_module.load(CONFIG)
    device = li.find_device(config.device_match)
    if device is None:
        return guide.DEFAULT_LAYOUT
    try:
        profile_name, _, _ = config.profile_for(device.name, device.vid_pid)
        return config.badge_layout(profile_name)
    finally:
        device.close()


def label(button, layout):
    """One button, printed. The D-pad has no letters on any pad, so it is
    named as well as drawn - "D-pad ▲" rather than a bare arrow."""
    badge = guide.badge_of(button, layout)
    if button.startswith("DPAD_"):
        return "D-pad %s" % badge
    return badge


class Director:
    """Drives the pad and keeps the cue log."""

    def __init__(self, pad, layout):
        self.pad = pad
        self.layout = layout
        self.log = open(CUES, "w")

    # -- captions ----------------------------------------------------------

    def cue(self, text, buttons=(), free=None, note=None, join=" + ",
            chapter=None):
        """Put a caption up; it stays until the next cue or `clear()`.

        `buttons` are logical names and become badges. `free` is for what no
        badge covers - a stick, an instruction - and `note` is the parenthesis
        a held button earns.
        """
        keys = free
        if buttons:
            keys = join.join(label(name, self.layout) for name in buttons)
        if keys and note:
            keys = "%s (%s)" % (keys, note)
        self._write({"keys": keys, "text": text, "chapter": chapter})

    def clear(self):
        self._write({"keys": None, "text": None, "chapter": None})

    def _write(self, entry):
        entry["t"] = time.monotonic()
        self.log.write(json.dumps(entry) + "\n")
        self.log.flush()

    # -- the pad, with a beat between presses so a viewer can follow -------

    def tap(self, button, pause=0.55, times=1):
        for _ in range(times):
            self.pad.tap(button)
            time.sleep(pause)

    def hold(self, button, seconds):
        self.pad.down(button)
        time.sleep(seconds)
        self.pad.up(button)

    def wait(self, seconds):
        time.sleep(seconds)


# ---------------------------------------------------------------------------
# The beats. One function per chapter; `record.sh SCENE...` runs a subset.
# ---------------------------------------------------------------------------


def scene_intro(d):
    d.cue("gamepadd — the Hyprland desktop, from the couch",
          chapter="intro")
    d.wait(3.0)
    d.cue("A user-space daemon and an Omarchy shell plugin. "
          "Python standard library only, no compositor patches.",
          chapter="intro")
    d.wait(3.4)
    d.clear()
    d.wait(0.6)


def scene_pointer(d):
    # The pointer was parked in the top-left corner before the recorder
    # started, so this path lands in the same places on every take.
    d.cue("The pointer. Nothing to aim with but a thumb.",
          free="Left stick", chapter="pointer")
    d.pad.stick_hold("L", 0.95, 0.45, 1.5)
    d.pad.stick_hold("L", 0.35, -0.85, 0.7)
    d.pad.stick_hold("L", -0.7, 0.3, 0.6)
    d.pad.stick_hold("L", 0.5, 0.5, 0.6)
    d.pad.rest()
    d.wait(0.4)

    # Over the terminal, where a click costs nothing. Aimed rather than left
    # where the sweep ended: a click landing in the file manager would open
    # whatever was under it and take the set apart.
    d.cue("Left click.", buttons=["ZR"], chapter="pointer")
    d.tap("ZR", pause=1.0)

    # Back over the file manager, which has something to scroll.
    d.pad.stick_hold("L", -1.0, 0.0, 1.3)
    d.cue("Scroll, with a ramp that follows how far the thumb went.",
          free="Right stick", chapter="pointer")
    d.pad.stick_hold("R", 0, 0.85, 1.8)
    d.pad.stick_hold("R", 0, -0.85, 1.5)
    d.pad.rest()
    d.wait(0.4)
    d.clear()
    d.wait(0.5)


def scene_workspaces(d):
    d.cue("Previous / next workspace. The pad ticks as it goes.",
          buttons=["L", "R"], join=" / ", chapter="workspaces")
    d.tap("R", pause=1.1, times=2)
    d.tap("L", pause=1.1, times=2)
    d.clear()
    d.wait(0.4)


def scene_window_layer(d):
    d.cue("The window layer. A modifier held by a finger that is not a thumb,"
          " because inside it both thumbs are busy.",
          buttons=["ZL"], note="hold", chapter="window")
    d.pad.down("ZL")
    d.wait(1.6)

    # Right, left, right: it ends on the terminal whatever had focus when the
    # scene started, so the keyboard scene types somewhere known.
    d.cue("Focus the window in that direction.",
          buttons=["ZL", "DPAD_RIGHT"], chapter="window")
    d.tap("DPAD_RIGHT", pause=1.0)
    d.tap("DPAD_LEFT", pause=1.0)
    d.tap("DPAD_RIGHT", pause=1.0)

    d.cue("Fullscreen.", buttons=["ZL", "A"], chapter="window")
    d.tap("A", pause=1.5)
    d.tap("A", pause=1.1)

    d.cue("Float / tile.", buttons=["ZL", "X"], chapter="window")
    d.tap("X", pause=1.4)
    d.tap("X", pause=1.1)

    d.cue("Send the window to the next workspace.",
          buttons=["ZL", "R"], chapter="window")
    d.tap("R", pause=1.5)
    d.cue("And bring it back.", buttons=["ZL", "L"], chapter="window")
    d.tap("L", pause=1.4)

    d.pad.up("ZL")
    d.clear()
    d.wait(0.5)


def scene_keyboard(d):
    d.cue("The on-screen keyboard. Its layout and latches live in the daemon,"
          " so a keypress never waits on the shell.",
          buttons=["MINUS"], chapter="keyboard")
    d.tap("MINUS", pause=1.8)

    # From "Tab" (row 1, column 0) down to the home row and out to "l":
    # Caps a s d f g h j k l ; Enter.
    d.cue("Move the selection.", buttons=["DPAD_RIGHT"], chapter="keyboard")
    d.tap("DPAD_DOWN", pause=0.45)
    d.tap("DPAD_RIGHT", pause=0.28, times=9)
    d.wait(0.5)

    d.cue("Press the key under it.", buttons=["A"], chapter="keyboard")
    d.tap("A", pause=0.9)
    d.tap("DPAD_LEFT", pause=0.24, times=7)
    d.tap("A", pause=0.9)

    d.cue("Shift, for as long as it is held - a whole capitalised word costs "
          "one finger.", buttons=["ZL"], note="hold", chapter="keyboard")
    d.pad.down("ZL")
    d.wait(2.0)
    d.pad.up("ZL")
    d.wait(0.7)

    d.cue("Walk the pages: letters, symbols, function keys.",
          buttons=["L", "R"], join=" / ", chapter="keyboard")
    d.tap("R", pause=1.4)
    d.tap("R", pause=1.4)
    d.tap("L", pause=1.1)
    d.tap("L", pause=1.1)

    d.cue("Enter, and the keyboard puts itself away.",
          buttons=["ZR"], chapter="keyboard")
    d.tap("ZR", pause=2.0)
    d.clear()
    d.wait(0.6)


def scene_menu(d):
    d.cue("The controller menu. A chord, so it is still reachable while a "
          "game holds the pad.",
          buttons=["MINUS", "PLUS"], chapter="menu")
    d.pad.chord("MINUS", "PLUS")
    d.wait(1.9)

    d.cue("Walk the rows. It always opens at its root.",
          buttons=["DPAD_DOWN"], chapter="menu")
    d.tap("DPAD_DOWN", pause=0.5, times=6)
    d.wait(0.6)

    d.cue("Into the Controller submenu.", buttons=["A"], chapter="menu")
    d.tap("A", pause=1.5)

    d.cue("Button labels: which console's printing the badges carry.",
          buttons=["DPAD_DOWN", "A"], chapter="menu")
    d.tap("DPAD_DOWN", pause=0.5, times=3)
    d.tap("A", pause=1.6)
    d.wait(0.9)

    d.cue("Back out a level.", buttons=["B"], chapter="menu")
    d.tap("B", pause=1.3)
    d.clear()
    d.wait(0.4)


def scene_guide(d):
    # `move()` wraps, so the walk back to the first row is counted, not
    # spammed until it clamps.
    d.cue("Back to the first row.", buttons=["DPAD_UP"], chapter="guide")
    d.tap("DPAD_UP", pause=0.45, times=3)

    d.cue("Shortcuts — the bindings guide, badged for the pad in your "
          "hands rather than the one it was written on.",
          buttons=["A"], chapter="guide")
    d.tap("A", pause=2.2)

    d.cue("Turn its pages: the base layer, the window layer, the keyboard, "
          "the menu.", buttons=["L", "R"], join=" / ", chapter="guide")
    d.tap("R", pause=2.1)
    d.tap("R", pause=2.1)
    d.tap("L", pause=1.7)

    d.cue("Close it.", buttons=["B"], chapter="guide")
    d.tap("B", pause=1.3)
    d.clear()
    d.wait(0.4)


def scene_game_mode(d):
    d.cue("Game mode: the same desktop, read from further away. Every "
          "binding, layer and profile still works.",
          buttons=["HOME"], note="hold", chapter="game")
    d.hold("HOME", 1.1)
    d.wait(2.2)

    d.cue("The bar says what every button does right now, in whichever layer "
          "is live.", chapter="game")
    d.wait(2.2)

    d.cue("Hold the layer and the bar re-reads itself.",
          buttons=["ZL"], note="hold", chapter="game")
    d.pad.down("ZL")
    d.wait(2.4)
    d.pad.up("ZL")
    d.wait(0.9)

    d.cue("And back to the desktop.",
          buttons=["HOME"], note="hold", chapter="game")
    d.hold("HOME", 1.1)
    d.wait(1.8)
    d.clear()
    d.wait(0.4)


def scene_mapping(d):
    d.cue("One last row in the menu: the mapping screen.",
          buttons=["MINUS", "PLUS"], chapter="mapping")
    d.pad.chord("MINUS", "PLUS")
    d.wait(1.5)
    d.tap("DPAD_DOWN", pause=0.32, times=6)
    d.tap("A", pause=1.2)
    d.tap("DPAD_DOWN", pause=0.32, times=5)

    d.cue("Remap the buttons.", buttons=["A"], chapter="mapping")
    d.tap("A", pause=2.3)

    d.cue("It reads the pad raw and writes down the code that arrives — "
          "the answer to a pad that prints one thing and sends another.",
          free="Press what it asks for", chapter="mapping")
    for button in ("A", "B", "X", "Y"):
        d.pad.tap(button)
        time.sleep(0.9)
    d.wait(1.2)

    d.cue("The way out that needs no map. Nothing is written.",
          free="Hold any button", chapter="mapping")
    d.hold("A", 3.0)
    d.wait(1.8)
    d.clear()
    d.wait(0.5)


def scene_outro(d):
    d.cue("Surface state lives in the daemon. The plugin only draws — "
          "and the daemon keeps running without it.", chapter="outro")
    d.wait(3.6)
    d.cue("gamepadd", chapter="outro")
    d.wait(2.2)
    d.clear()
    d.wait(0.8)


SCENES = (
    scene_intro,
    scene_pointer,
    scene_workspaces,
    scene_window_layer,
    scene_keyboard,
    scene_menu,
    scene_guide,
    scene_game_mode,
    scene_mapping,
    scene_outro,
)


# ---------------------------------------------------------------------------


def start_daemon():
    """The daemon, on the demo pad and the demo config.

    Started here rather than beside the recorder because the pad has to exist
    first: `find_device` runs once, at connect time, and a daemon that started
    before /dev/uinput handed the node over would attach to the real pad.
    """
    from omapad import control

    handle = open(os.path.join(HERE, "daemon.log"), "w")
    process = subprocess.Popen(
        [os.path.join(REPO, "bin", "omapad"), "-c", CONFIG, "run"],
        stdout=handle, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + DAEMON_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(0.25)
        try:
            reply = control.send("status")
        except OSError:
            continue
        if "device=omapad demo pad" in reply:
            return process
    process.terminate()
    raise SystemExit("the daemon never came up on the demo pad - see "
                     "demo/daemon.log")


def parse(argv):
    """`--go <path>` takes a value, so this cannot just keep every argument
    that is not a flag: the path would read as a scene name."""
    scenes, go, index = [], None, 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--go":
            go = argv[index + 1]
            index += 2
            continue
        if not arg.startswith("-"):
            scenes.append(arg)
        index += 1
    return scenes, go


def main():
    only, go = parse(sys.argv[1:])
    known = dict((s.__name__[len("scene_"):], s) for s in SCENES)
    for name in only:
        if name not in known:
            raise SystemExit("no such scene: %s (have %s)"
                             % (name, ", ".join(sorted(known))))

    pad = pad_module.VirtualPad()
    daemon = start_daemon()
    director = Director(pad, badge_layout())
    # A resting report first, and only then anything that moves. The daemon
    # scales each axis around the first value it sees for it - the advertised
    # centre is a claim, not a measurement - so a stick whose first sample was
    # a flick would spend the whole take reading that flick as its neutral.
    pad.rest()
    time.sleep(0.8)
    # The pointer is wherever the last person left it, and the first scene is
    # a path across the screen. Park it in a corner while nothing is being
    # recorded, so that path starts from the same place every take.
    pad.stick_hold("L", -1.0, -1.0, 1.8)
    pad.rest()
    print("READY", flush=True)
    if go:
        # The recorder wants a settled desktop in its first frame, so the
        # scenes wait on it rather than the other way round.
        while not os.path.exists(go):
            time.sleep(0.1)

    try:
        for scene in SCENES:
            name = scene.__name__[len("scene_"):]
            if only and name not in only:
                continue
            print("-> %s" % name, flush=True)
            scene(director)
    finally:
        director.clear()
        director.log.close()
        pad.rest()
        daemon.terminate()
        try:
            daemon.wait(timeout=5)
        except subprocess.TimeoutExpired:
            daemon.kill()
        pad.close()
    print("cues written to %s" % CUES)


if __name__ == "__main__":
    main()
