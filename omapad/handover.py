"""Who wants the pad: the app in front, or us.

Game mode is the couch environment, not a hand-off - omapad drives the
desktop there, only bigger. Handing the pad to a game is a separate thing, and
it should not be a mode anybody has to remember to switch: there are a million
games and no list of them is going to stay right.

So ask the program instead of guessing at it. A gamepad on Linux is a file, and
anything that wants to read one has to open it. The kernel keeps that list and
`/proc` shows it, so "has the focused app opened the pad?" is a question with a
real answer - and it is exactly the question. A terminal never opens it. A
browser opens it the moment a page asks for a gamepad and not before, which is
precisely when a cloud session wants it. A game opens it because that is what a
game does.

Four details stop the simple version from working:

- **Steam does not open the event node at all.** It reads controllers through
  `hidraw`, so a check that watched only /dev/input would decide Steam had
  never asked for the pad and would never hand it over - measured here, with
  Steam holding /dev/hidraw1 and nothing under /dev/input.

- Steam holds every input device open for as long as it runs, focused or not,
  so "somebody has it open" is true all evening. The question has to be about
  the window in front.
- Steam then launches the game as a separate process, and a window's pid is
  not always the process that opened the device - a launcher, a wrapper script
  and the game itself are three pids. So the whole process tree around the
  focused window counts, not just its own pid.

- **The process that opens it is not always above or below the window's.**
  Under Proton it is `winedevice.exe`, wine's HID service, which is a sibling
  of the game's process. So the walk goes sideways as well - bounded by the
  cgroup, since a terminal's siblings are the whole desktop. See `related`.

- **And the launchers between Steam and the game are deeper than any count.**
  `steam -> srt-bwrap -> pv-adverb -> steamwebhelper` is three before the
  game's own wrapper, so a walk bounded by generations reached Steam from
  Steam's window and never from the game it started: the pad stayed ours, the
  grab kept it from the game, and every stick went on driving the desktop over
  the top of it. The cgroup is the bound that fits, because systemd gives a
  launched application its own scope and everything Steam starts stays in it.

`EVIOCGRAB` blocks events, not opens, so all of this stays visible while
omapad holds the pad: the app opens the device, gets nothing, and we notice
and let go.
"""

import os

PROC = "/proc"


def device_nodes(path):
    """Every node one physical pad answers on.

    Three kinds, and missing any of them means missing the app that wanted the
    pad:

    - the event node evdev clients read;
    - the `js*` node joydev exposes, which is still the older and commoner
      answer for a lot of game libraries;
    - the `hidraw` node of the HID device underneath both. This is the one
      that matters most in practice: **Steam reads controllers through
      hidraw**, so a check that watched only /dev/input would decide Steam
      had never asked for the pad and would never hand it over. Measured
      rather than assumed - Steam holds /dev/hidraw1 on this machine while
      holding nothing under /dev/input.
    """
    nodes = {path}
    name = os.path.basename(path)
    device = os.path.join("/sys/class/input", name, "device")
    try:
        for entry in os.listdir(device):
            if entry.startswith(("event", "js")):
                nodes.add(os.path.join("/dev/input", entry))
    except OSError:
        pass
    nodes |= _hidraw_nodes(device)
    return nodes


def _hidraw_nodes(device):
    """The hidraw nodes of the HID device this input node hangs off.

    The input node sits at `<hid device>/input/inputN`, so the HID device -
    which is what carries `hidraw/` - is a couple of levels up. Walked rather
    than hard-coded, since the depth is not promised anywhere.
    """
    found = set()
    walker = device
    for _ in range(4):
        walker = os.path.dirname(os.path.realpath(walker))
        if walker in ("/", ""):
            break
        candidate = os.path.join(walker, "hidraw")
        try:
            entries = os.listdir(candidate)
        except OSError:
            continue
        for entry in entries:
            if entry.startswith("hidraw"):
                found.add(os.path.join("/dev", entry))
        if found:
            break
    return found


def holders(nodes, skip_pid=None, proc=PROC):
    """The pids with any of these nodes open, ours excluded.

    A scan of /proc, which is cheap enough at the rate focus changes and far
    cheaper than being wrong about which app owns the pad.
    """
    found = set()
    skip = str(skip_pid) if skip_pid is not None else None
    try:
        entries = os.listdir(proc)
    except OSError:
        return found
    for entry in entries:
        if not entry.isdigit() or entry == skip:
            continue
        fddir = os.path.join(proc, entry, "fd")
        try:
            descriptors = os.listdir(fddir)
        except OSError:
            continue  # gone, or not ours to look at
        for descriptor in descriptors:
            try:
                target = os.readlink(os.path.join(fddir, descriptor))
            except OSError:
                continue
            if target in nodes:
                found.add(int(entry))
                break
    return found


def parent_of(pid, proc=PROC):
    """The pid's parent, from /proc/<pid>/stat, or None."""
    try:
        with open(os.path.join(proc, str(pid), "stat")) as handle:
            text = handle.read()
    except OSError:
        return None
    # The command sits in brackets and may contain spaces; everything after the
    # closing bracket is fixed-width, and ppid is the second field of it.
    close = text.rfind(")")
    if close < 0:
        return None
    fields = text[close + 2:].split()
    if len(fields) < 2:
        return None
    try:
        parent = int(fields[1])
    except ValueError:
        return None
    return parent or None


def children_of(pid, proc=PROC):
    """Direct children, from the thread's `children` file."""
    out = set()
    taskdir = os.path.join(proc, str(pid), "task")
    try:
        threads = os.listdir(taskdir)
    except OSError:
        return out
    for thread in threads:
        try:
            with open(os.path.join(taskdir, thread, "children")) as handle:
                text = handle.read()
        except OSError:
            continue
        for word in text.split():
            try:
                out.add(int(word))
            except ValueError:
                pass
    return out


def cgroup_of(pid, proc=PROC):
    """The unified cgroup a pid sits in, or None.

    The systemd desktop already answers "which processes are one app": each
    launched thing gets its own scope under `app.slice`, and a Steam game gets
    one that holds its whole wine session. That is the boundary the process
    tree does not have, and the sideways step in `related` needs it - without
    one, "beside the window's process" means "every window on the screen".
    The root cgroup - or no cgroup at all, on a machine that does not do this
    - is no boundary, and reads as none.
    """
    try:
        with open(os.path.join(proc, str(pid), "cgroup")) as handle:
            text = handle.read()
    except OSError:
        return None
    for line in text.splitlines():
        # `0::<path>` is the unified hierarchy; the numbered v1 lines say
        # nothing about which app a process belongs to.
        parts = line.split(":", 2)
        if len(parts) == 3 and parts[0] == "0":
            path = parts[2].strip()
            if path and path != "/":
                return path
    return None


def _descend(start, levels, seen, proc, scope=None):
    """Add up to `levels` generations below `start` to `seen`.

    `scope`, when given, keeps the walk inside one cgroup: a process outside
    it is neither counted nor walked through.
    """
    frontier = {start}
    for _ in range(levels):
        following = set()
        for entry in frontier:
            for child in children_of(entry, proc) - seen:
                if scope is not None and cgroup_of(child, proc) != scope:
                    continue
                following.add(child)
        if not following:
            break
        seen |= following
        frontier = following


def related(pid, proc=PROC, depth=3, siblings=True):
    """The focused window's process, its ancestors, and everything beside it.

    Bounded above by the cgroup and below by `depth`. Above it has to be the
    cgroup: a launcher three deep was thought to be the shape (Steam ->
    reaper -> wrapper -> game) and a game under Proton is half as deep again,
    while a session leader eight deep is just `systemd` and walking to it
    would hand the pad over for every window on the desktop. A count cannot
    tell those apart and the scope does not have to - it ends where the
    application ends, however many launchers that took.

    Sideways too, and that is not decoration. Under Proton the process that
    opens the pad is `winedevice.exe` - wine's own HID service - and it is a
    *sibling* of the window's process rather than an ancestor or a child: both
    hang off the same pressure-vessel adverb. Measured with Balatro, which
    left a walk that only goes up and down deciding no one had asked for the
    pad while the game was in front of it.

    Stepping sideways needs a boundary, though: a terminal's parent is the
    compositor, so its siblings are every window on the screen, and a game
    running behind one of them would take the pad away from the terminal in
    front. The cgroup is that boundary - the step is taken only among
    processes that share the focused one's - and where there is no cgroup to
    read there is no step.
    """
    seen = {int(pid)}
    scope = cgroup_of(pid, proc) if siblings else None
    ancestry = []
    walker = int(pid)
    # The climb is bounded by the cgroup where there is one, and only by
    # `depth` where there is not. Counting generations was the first answer
    # and it cannot reach a game under Proton: measured here, `steam ->
    # srt-bwrap -> pv-adverb -> steamwebhelper` is already three, and a game
    # adds the reaper and wine's own wrapper below that. No count that reached
    # it would be safe either - the same number applied to a terminal walks to
    # the compositor, whose descendants are every window on the screen. The
    # scope has no such problem: it is exactly as long as the application is.
    while True:
        if scope is None and len(ancestry) >= depth:
            break
        parent = parent_of(walker, proc)
        if parent is None or parent == 1:
            break
        if scope is not None and cgroup_of(parent, proc) != scope:
            break
        ancestry.append(parent)
        seen.add(parent)
        walker = parent
    # What hangs off the window's own process is the app whatever any cgroup
    # says. What hangs off its launchers is the app only while it is both
    # inside the same scope and inside the same neighbourhood, so the budget
    # shrinks with every step up - and runs out, which is what keeps a long
    # climb from dragging a launcher's whole subtree in with it.
    _descend(int(pid), depth, seen, proc)
    if scope:
        for height, start in enumerate(ancestry, 1):
            _descend(start, depth - height, seen, proc, scope)
    return seen


def wants_pad(focus_pid, nodes, skip_pid=None, proc=PROC, depth=3,
              siblings=True):
    """Has the window in front - or its process tree - opened the pad?"""
    if not focus_pid:
        return False
    open_by = holders(nodes, skip_pid=skip_pid, proc=proc)
    if not open_by:
        return False
    return bool(open_by & related(focus_pid, proc, depth, siblings))
