"""Writing the systemd user unit, with this checkout's path baked in.

Installing the unit is a template and a path, and both halves used to be one
line of shell: `sed "s|__REPO__|$REPO|g" ... > "$UNIT_DIR/omapad.service"`.

A path is not replacement syntax. In a `sed` replacement `&` means the whole
match, `|` ends the expression, a backslash escapes the next character and a
newline ends the command - so a checkout path carrying any of them writes a
unit nobody wrote. And `>` opens the destination through whatever name is
already there: a symlink planted at `omapad.service` made the installer
truncate and rewrite what it pointed at, and an interruption between the open
and the last byte left a half-written unit where systemd would read it.

So the substitution here is a literal `str.replace`, a path that cannot be
baked in unchanged is refused rather than escaped, and the file lands by
renaming a sibling temporary file over the name - which replaces the name
itself instead of writing through it, is atomic for a reader, and leaves the
unit that was already there when anything on the way fails.
"""

import os
import re
import stat
import tempfile

NAME = "omapad.service"
MARKER = "__REPO__"

# The mode a unit is read with: systemd only ever reads it, and the directory
# is the user's own. Not a setting - a unit nobody can read is not installed.
MODE = 0o644

# A unit is a page of text. A larger file is not the template this bakes a
# path into, and refusing to read it whole is what keeps everything below a
# decision about bytes that are known.
MAX_TEMPLATE = 64 * 1024

# What a checkout path may contain, and it is the unit's own grammar that
# decides: systemd splits `ExecStart` on whitespace and reads `%` as a
# specifier, so a path with either in it cannot be baked in at all - not
# quoted, not escaped. Everything else refused here is a character that meant
# something to one of the layers this path has passed through (`sed`, the
# shell, a here-document), and a checkout is somewhere the user chose, so
# saying which characters are impossible costs them a `mv` and nothing else.
SAFE = re.compile(r"\A/[A-Za-z0-9/._+@:=,-]*\Z")


class UnitError(Exception):
    """The unit could not be installed, and nothing on disk was changed.

    Every raise below happens either before the destination is touched or
    while a temporary file is still the only thing written, so the caller can
    report this and leave the machine as it was.
    """


def checkout():
    """The checkout this module was imported from.

    Asked of the package rather than passed in from the installer: the path
    that ends up in `ExecStart` is then the path Python is actually running
    from, and there is one less place for it to be rewritten on the way.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def unit_dir():
    """Where systemd looks for this user's units."""
    if os.environ.get("OMAPAD_UNIT_DIR"):
        return os.environ["OMAPAD_UNIT_DIR"]
    config = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(config, "systemd", "user")


def check_repo(repo):
    """Return `repo`, or raise unless it survives being written into a unit."""
    if not SAFE.match(repo or ""):
        raise UnitError(
            "the checkout path %r cannot be written into a systemd unit - it "
            "must be absolute and hold only letters, digits and ._+@:=,-/ "
            "(a space or a %% has no meaning ExecStart would keep). Move the "
            "checkout somewhere simpler and run this again." % (repo or "")
        )
    return repo


def read_template(path):
    """The unit template, bounded, so what is rendered is a known quantity."""
    with open(path) as stream:
        text = stream.read(MAX_TEMPLATE + 1)
    if len(text) > MAX_TEMPLATE:
        raise UnitError("%s is larger than %d bytes, so it is not the unit "
                        "template" % (path, MAX_TEMPLATE))
    return text


def render(template, repo):
    """`template` with `MARKER` replaced by `repo`, as data and only as data."""
    check_repo(repo)
    if MARKER not in template:
        raise UnitError("the unit template names no %s, so there is nothing "
                        "to bake the checkout path into" % MARKER)
    return template.replace(MARKER, repo)


def refuse_planted(dest):
    """Raise unless `dest` is a regular file, or nothing at all.

    `rename` replaces the name and never follows a symlink sitting at it, so
    this is not what makes the write safe - it is what stops it being silent.
    A symlink or a socket at `omapad.service` is either someone else's or an
    install of a kind this has never made, and both are worth stopping for.
    """
    try:
        info = os.lstat(dest)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode):
        raise UnitError("%s is a symlink; refusing to install a unit over it"
                        % dest)
    if not stat.S_ISREG(info.st_mode):
        raise UnitError("%s is not a regular file; refusing to install a unit "
                        "over it" % dest)


def install(text, dest, mode=MODE):
    """Land `text` at `dest` atomically, without ever writing through it."""
    directory = os.path.dirname(dest) or "."
    os.makedirs(directory, exist_ok=True)
    # In the destination's own directory, so the rename below is a rename and
    # not a copy: mkstemp creates it exclusively under a name nobody can have
    # planted, which is the half a plain redirection never had.
    handle, temporary = tempfile.mkstemp(prefix=".%s." % NAME, dir=directory)
    try:
        with os.fdopen(handle, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        refuse_planted(dest)
        os.rename(temporary, dest)
    except BaseException:
        # BaseException, not Exception: a Ctrl-C anywhere above is the
        # interruption this shape exists for, and the temporary file must not
        # outlive it in a directory systemd reads.
        remove(temporary)
        raise
    sync_dir(directory)
    return dest


def verify(text, dest):
    """Read the unit back before anything acts on it.

    The same move the udev rule makes in `install.sh`: `systemctl
    daemon-reload` is what makes a unit real, and a unit that is not the one
    written here must never get that far.
    """
    with open(dest) as stream:
        found = stream.read(MAX_TEMPLATE + 1)
    if found != text:
        raise UnitError("%s is not the unit just written to it" % dest)


def install_service(repo=None, dest=None):
    """Render the unit for `repo` and install it, returning where it landed."""
    repo = check_repo(repo or checkout())
    dest = dest or os.path.join(unit_dir(), NAME)
    text = render(read_template(os.path.join(repo, "systemd", NAME)), repo)
    install(text, dest)
    verify(text, dest)
    return dest


def remove(path):
    """Best-effort: the failure being cleaned up after is the one to report."""
    try:
        os.unlink(path)
    except OSError:
        pass


def sync_dir(path):
    """Make the rename durable; a crash otherwise leaves neither unit.

    Best-effort because some filesystems refuse to sync a directory, and a
    unit that is on disk but not yet flushed is still a unit that works.
    """
    try:
        handle = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(handle)
    except OSError:
        pass
    finally:
        os.close(handle)
