# What is installed - `omapad/apps.py`

The applications the Add picker offers, what an app put on a page runs, and
what an `apps` tile (`Apps > All apps`) opens.
A **source rather than a surface**, the shape [`live.md`](live.md) and
[`snap.md`](snap.md) have: no socket and no control verb, because nothing
here is drawn. Decision [100](../decisions/100-one-button-that-adds.md) is
why it exists.

## Omarchy's rules, not the shell's list

Omarchy's app launcher already answers "what is installed", in QML: its
`AppLibrary` is `DesktopEntries` minus what it hides. That list is handed to
plugins whose manifest says `menu`, and this one is a `panel` - and even as a
menu it would be the wrong side: the menu's state is the daemon's, and a page
must be arrangeable, and an app on it drawn, with the shell down. So the list
is read here, and **what is reused is every rule the launcher applies**:

| The launcher's | Here |
|---|---|
| entries under each `applications/` on the XDG data path, the user's first | `data_dirs()`, in the order `hidden-entries.sh` walks them, `~/.nix-profile` included |
| a desktop id is the path under that directory with `/` as `-` | `desktop_id()` |
| `shell/services/hidden-entries.sh` says what is hidden, `OnlyShowIn` and `NotShowIn` included | **run as it is**, with the session's desktop names - `omarchy_hidden()` |
| `default/omarchy/launcher.hides` names more, with or without `.desktop` | read as it is |
| `uwsm-app -- gtk-launch <id>.desktop` starts one | `launch()` |
| `iconSource()`: a path is a file, a name is looked up in the theme, nothing found is `application-x-executable` | `appIcon()` in `Menu.qml` - the panel's half, since the theme in force is the panel's |

So an app hidden from the launcher is hidden from the picker, and one the
launcher starts is started the same way. `NoDisplay` and `Hidden` are asked
here as well, so a desktop without Omarchy still leaves out what every
launcher does.

## A command, off the loop

Reading sixty entries is 30 ms and the hiding script is 300. `python3 -m
omapad.apps` prints one line per app - `id`, `kind`, `name`, `icon`,
`wmclass`, tab-separated - and the daemon runs it (`apps.command()`, this
interpreter and this checkout) on the command worker every listing runs on.
`parse()` reads it back, **padding a short line**: the worker strips what it
reads, which takes the trailing tabs of an entry with no icon or no window
class with it. That was a bug for an afternoon - 17 of 44 apps - and the test
that strips the line is why it stays fixed.

`Daemon.apps_refresh()` asks when the loop starts and whenever rearranging
begins, which is the moment somebody may be about to open the picker, and
at every press of an `apps` tile - which is built from the index already
read, so the press does not wait and the answer is the next visit's. Not in
the constructor: every test builds a daemon, and none of them may start a
subprocess. One read at a time, however often it is asked.

## Kinds

`KINDS` folds the freedesktop registry into the handful of doors a console's
library has - Games, Music and video, Internet, Office, Graphics,
Development, System - with Other for the rest. First match wins, so a game
that also calls itself a utility is a game. An Omarchy webapp names no
category at all and is a website, so an entry whose `Exec` runs
`omarchy-launch-webapp` is Internet. `by_kind()` leaves out a kind with
nothing in it: a door that opens on nothing is worse from a sofa than no
door.

Not a setting. It is a file format's vocabulary read into words a picker
prints; an app somebody wants elsewhere they put elsewhere once it is on a
page.
