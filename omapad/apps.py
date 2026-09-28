"""What is installed, read the way Omarchy's own launcher reads it.

A tile put on a page from the pad has to be something a thumb can choose from
a list, and the list the rest of this desktop already agrees on is the one
Omarchy's app launcher shows: its `AppLibrary` is the freedesktop entries
under every `applications/` directory on the XDG data path, minus what its
own `hidden-entries.sh` says is hidden and what `launcher.hides` names.

**Omarchy's rules, not the shell's copy of the list.** The shell holds that
list in QML (`DesktopEntries`) and hands it only to plugins that *are* a
menu; this one is a panel, and the menu's state lives in the daemon, where a
page has to be arrangeable with the shell down. So what is reused is the
part that is a rule rather than a list - the hiding script is run as it is,
the hides file read as it is, and a desktop id is built the way that script
builds one - and what launches an app is the command `AppLibrary.launch`
runs. A person who hides an app from the launcher hides it here too.

**Run as a command, off the loop.** Reading sixty entries is 30 ms and the
hiding script is 300, which is a press that waits. `python3 -m omapad.apps`
prints one tab-separated line per app, and the daemon runs it on the
command worker every other shell command a surface asks for runs on.

The icon itself is found by the panel: resolving an icon theme is a question
about the theme in force, and the panel is the one that draws in it.
"""

import configparser
import os
import re
import shlex
import subprocess
import sys

# The categories the picker offers, in the order it offers them, and which of
# the freedesktop registry's names each one takes. The registry has a dozen
# main categories and a long tail of additional ones; from a sofa that is too
# many doors, so they are folded into the handful a console's own library is
# cut into. The first match wins, so an entry that is both a game and a
# utility is a game.
#
# Not a setting: this is a file format's vocabulary read into the words a
# picker prints, and a person who wants an app somewhere else puts it there
# once it is on a page.
KINDS = (
    ("games", "Games", ("Game",)),
    ("media", "Music and video", ("AudioVideo", "Audio", "Video")),
    ("internet", "Internet", ("Network", "WebBrowser", "Chat", "Email")),
    ("office", "Office", ("Office",)),
    ("graphics", "Graphics", ("Graphics",)),
    ("development", "Development", ("Development",)),
    ("system", "System", ("System", "Settings")),
)

# Where an entry that names none of the above goes.
OTHER = ("other", "Other")

# An Omarchy webapp names no category at all - the installer writes a name,
# an icon and a command - and is a website, which is to say the internet.
# Asked of the command because that is the one thing every webapp entry has
# in common.
WEBAPP = re.compile(r"\bomarchy-launch-webapp\b")

SECTION = "Desktop Entry"

# Where Omarchy keeps what its launcher hides, relative to `OMARCHY_PATH`.
# Both are Omarchy's, named the way `AppLibrary.qml` names them, and both
# are optional: a desktop without Omarchy still has entries to offer.
HIDDEN_SCRIPT = os.path.join("shell", "services", "hidden-entries.sh")
HIDES_FILE = os.path.join("default", "omarchy", "launcher.hides")

# How long the hiding script may take before its answer is done without. It
# reads every entry with bash; 300 ms here.
HIDDEN_TIMEOUT = 5.0


def data_dirs():
    """The `applications/` directories, nearest first - the script's order.

    The user's own before the system's: an entry of the same id in
    `~/.local/share/applications` is how a person overrides or hides one the
    system shipped, and the first one found is the one that counts.
    """
    home = os.path.expanduser("~")
    rest = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    bases = [os.path.join(home, ".local", "share")] + rest.split(":")
    out = []
    for base in bases:
        if not base:
            continue
        path = os.path.join(base, "applications")
        if path not in out:
            out.append(path)
    nix = os.path.join(home, ".nix-profile", "share", "applications")
    if nix not in out:
        out.append(nix)
    return out


def desktop_id(folder, path):
    """What the desktop calls the entry at `path`: `kde-foo` for `kde/foo`.

    The freedesktop rule, and the one `hidden-entries.sh` applies, so an id
    this module offers is an id that script can have hidden.
    """
    rel = os.path.relpath(path, folder)
    if rel.endswith(".desktop"):
        rel = rel[:-len(".desktop")]
    return rel.replace(os.sep, "-")


def read_entry(path):
    """One `.desktop` file's `[Desktop Entry]` group, or None.

    configparser with interpolation off - `%U` and `%f` are field codes, not
    interpolations - and every key kept as written, since `Name[tr]` and
    `Name` are different keys.
    """
    parser = configparser.RawConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            parser.read_file(handle)
    except (OSError, configparser.Error):
        return None
    if not parser.has_section(SECTION):
        return None
    return dict(parser.items(SECTION))


def _true(value):
    return str(value or "").strip().lower() == "true"


def kind_of(entry):
    """Which of `KINDS` an entry belongs to, as its id."""
    named = [part for part in (entry.get("Categories") or "").split(";")
             if part]
    for name, _, takes in KINDS:
        if any(part in takes for part in named):
            return name
    if WEBAPP.search(entry.get("Exec") or ""):
        return "internet"
    return OTHER[0]


def _files(folder):
    """Every entry under one directory, sorted the way the script sorts."""
    out = []
    for root, _, names in os.walk(folder):
        for name in names:
            if name.endswith(".desktop"):
                out.append(os.path.join(root, name))
    return sorted(out)


def installed(dirs=None, hidden=()):
    """Every application the launcher would offer, by desktop id.

    `{id: {"id", "name", "icon", "wmclass", "kind"}}`. `hidden` is the ids
    Omarchy's launcher leaves out; `NoDisplay` and `Hidden` are asked here as
    well, so that a desktop without the script still leaves out what every
    launcher does. An entry that is not an `Application`, or has no name, is
    not something to launch.
    """
    hidden = set(hidden)
    out = {}
    seen = set()
    for folder in dirs if dirs is not None else data_dirs():
        if not os.path.isdir(folder):
            continue
        for path in _files(folder):
            ident = desktop_id(folder, path)
            # The nearest one decides, including by being hidden: an entry
            # the user shadowed with `Hidden=true` must not come back from
            # the system's directory underneath it.
            if ident in seen:
                continue
            seen.add(ident)
            if ident in hidden:
                continue
            entry = read_entry(path)
            if entry is None:
                continue
            if (entry.get("Type") or "Application") != "Application":
                continue
            if _true(entry.get("NoDisplay")) or _true(entry.get("Hidden")):
                continue
            label = (entry.get("Name") or "").strip()
            if not label:
                continue
            out[ident] = {
                "id": ident,
                "name": label,
                "icon": (entry.get("Icon") or "").strip(),
                "wmclass": (entry.get("StartupWMClass") or "").strip(),
                "kind": kind_of(entry),
            }
    return out


def omarchy_hidden(root=None):
    """The ids Omarchy's launcher hides: its script's answer and its list.

    Run exactly as `AppLibrary.qml` runs it - non-login bash, the desktop's
    names as the one argument - because it is that file's rules that are
    wanted, including `OnlyShowIn` and `NotShowIn`, which only make sense
    against the names this session goes by. Nothing at all where Omarchy is
    not installed.
    """
    root = root if root is not None else os.environ.get("OMARCHY_PATH", "")
    if not root:
        return set()
    out = set()
    script = os.path.join(root, HIDDEN_SCRIPT)
    if os.path.isfile(script):
        names = ":".join(value for value in (
            os.environ.get("XDG_CURRENT_DESKTOP", ""),
            os.environ.get("XDG_SESSION_DESKTOP", ""),
            os.environ.get("DESKTOP_SESSION", "")) if value)
        try:
            done = subprocess.run(
                ["bash", "-c", "%s %s" % (shlex.quote(script),
                                          shlex.quote(names))],
                capture_output=True, text=True, timeout=HIDDEN_TIMEOUT)
            out.update(_ids(done.stdout))
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        with open(os.path.join(root, HIDES_FILE)) as handle:
            out.update(_ids(handle.read()))
    except OSError:
        pass
    return out


def _ids(text):
    """Desktop ids, one per line, with or without `.desktop` - Omarchy's
    `normalizeDesktopId`."""
    out = set()
    for line in text.splitlines():
        line = line.strip()
        if line.endswith(".desktop"):
            line = line[:-len(".desktop")]
        if line:
            out.add(line)
    return out


def launch(ident):
    """The shell command that starts one, as `AppLibrary.launch` starts it.

    `gtk-launch` resolves the entry - which copes with ids that have spaces
    in them and entries uwsm refuses - inside a scope of the app's own, and
    the `.desktop` is kept or an id like `org.telegram.desktop` would not
    resolve.
    """
    return "uwsm-app -- gtk-launch %s" % shlex.quote(ident + ".desktop")


# -- the wire between the command and the daemon -------------------------------

FIELDS = ("id", "kind", "name", "icon", "wmclass")


def lines(entries):
    """One tab-separated line per entry, sorted by id."""
    out = []
    for ident in sorted(entries):
        entry = entries[ident]
        out.append("\t".join(
            str(entry[field]).replace("\t", " ").replace("\n", " ")
            for field in FIELDS))
    return out


def parse(found):
    """The index back off the lines `lines` printed. A bad line is skipped.

    **Short lines are whole ones.** The command worker strips every line it
    reads, which takes the trailing tabs of an entry with no icon or no
    window class with it - so fewer fields than `FIELDS` is the empty ones
    at the end, and only more is a line that is not ours.
    """
    out = {}
    for line in found:
        parts = line.split("\t")
        if len(parts) > len(FIELDS):
            continue
        parts += [""] * (len(FIELDS) - len(parts))
        if not parts[0] or not parts[2]:
            continue
        out[parts[0]] = dict(zip(FIELDS, parts))
    return out


def command():
    """The shell command the daemon runs for the index.

    This interpreter and this checkout, rather than whatever `python3` is on
    the path: the module is only importable from where the daemon was.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return "PYTHONPATH=%s %s -m omapad.apps" % (
        shlex.quote(here), shlex.quote(sys.executable))


def kinds():
    """(id, words) for every category the picker can offer, in order."""
    return [(name, words) for name, words, _ in KINDS] + [OTHER]


def by_kind(entries):
    """The index cut into `kinds()`: (id, words, entries sorted by name).

    Only the categories with something in them: a door that opens on nothing
    is worse from a sofa than no door.
    """
    out = []
    for name, words in kinds():
        found = sorted((entry for entry in entries.values()
                        if entry["kind"] == name),
                       key=lambda entry: entry["name"].lower())
        if found:
            out.append((name, words, found))
    return out


def main():
    for line in lines(installed(hidden=omarchy_hidden())):
        print(line)


if __name__ == "__main__":
    main()
