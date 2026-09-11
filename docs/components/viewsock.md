# View socket - `omapad/viewsock.py`

69 lines, and one of the two load-bearing boundaries in the project.

## The contract

The daemon connects, as a client, to a socket the **plugin** listens on:
`$XDG_RUNTIME_DIR/omapad/<surface>.sock`, located by
[`paths.socket_path`](paths.md) - the daemon streams state into whatever
listens there, so the directory has to be one only this user can write to. It pushes one JSON object per
line, one line per state change, and re-sends everything every
`VIEW_HEARTBEAT` seconds.

```
osk.sock  menu.sock  guide.sock  mapping.sock  gamebar.sock  status.sock
ripple.sock
```

- **Either end may be up first, and neither waits.** The directory is the
  daemon's to make and the sockets are the plugin's to bind, so at login the
  plugin binds into a directory that is not there yet - Hyprland execs the
  shell the moment the compositor is up, while the service is still starting
  Python. Quickshell gives up after one failed bind, so the listening side's
  retry lives in `shell-plugin/SurfaceSocket.qml`; this side's is `connect()`
  on every `send`, plus the heartbeat.
- **`send` never raises.** It reconnects once on `EPIPE`/`ECONNRESET`/
  `ENOTCONN` - the shell restarting is normal, a theme change does it - and
  otherwise returns `False`.
- **The daemon does not wait for the view.** A keypress types through uinput
  and then the payload goes out; by the time the panel repaints, the character
  has already been typed.
- The heartbeat is what lets a restarted shell repaint itself with no
  handshake, and what takes a surface off the screen when the daemon stops
  talking.
- **The panel, not the daemon, decides that a line says nothing new.** Every
  push is the whole surface — with one exception, below — so a heartbeat and a
  press both hand the panel a
  great deal it already has. Sending a diff instead would cost the heartbeat
  its one job, so the filtering is on the drawing side: see
  [`../conventions/qml.md`](../conventions/qml.md) §5.4. Adding a field here
  needs nothing of the panel beyond a `fresh()` guard if it is a model.

## The one exception: a surface that streams

`menu.sock` carries a second, shorter line while a gauge is the tile in front:
`{open, sel, g, live}` and **no `items` key at all**. It is not a diff - it is
a different question, asked up to sixty times a second, and it is safe for
exactly one reason: with nothing on it that is a model, `applyState` never
reaches `fresh()`, so no delegate is rebuilt. The heartbeat still carries the
whole surface, so nothing here depends on the stream to be correct.

`sel` rides along rather than being inferred from the last full push: a stream
has to be meaningful on its own, so the panel never correlates two of them.
The floats are quantised in the daemon, which is what lets the daemon decline
to send a frame that says what the last one said. See
[`menu.md`](menu.md).

## `kind` means three things, and they are not the same thing

The word is spent three times across this tree, so which is which is written
down here rather than guessed at from a field name:

| Layer | Field | Means |
|---|---|---|
| config | `control` | which control a menu tile is |
| `menu.sock` | `k` | which tile to draw |
| `guide.sock`, `gamebar.sock` | `k` | which badge to draw |

The TOML word is `control` rather than `kind` for exactly this reason: `kind`
already had a meaning here, and a third one for the same word is the drift
[`../conventions/naming.md`](../conventions/naming.md) exists to stop.

## Payload rules

See [`../conventions/data.md`](../conventions/data.md). In short: field names
are short and stable, every field is optional and additive, and everything the
plugin needs - including the surface scale, the style its badges are drawn in
and the bar's own proportions - is in the payload, because the plugin cannot
read the config. `Daemon.scaled()` stamps the three that are nobody's own
state onto whatever a model returns, so no model has to remember them: `scale`,
`badge`, and `bar` for whether omapad's own bar is holding a strip of the
screen - which is what tells a scrim where to stop.

## What a device says about itself

`drawable(text)` is the one thing here that treats a string as coming from
outside the machine. A pad's name is a USB descriptor, an audio row's label is
whatever a sink was told to call itself, and both land in a shell that stays up
for the whole session. It cuts the string to `DRAWABLE` characters - a bound on
what a device may say, not a preference, and every row elides far short of it -
and drops `<` and `>`, which are what make Qt guess a string is rich text. The
panels all say `textFormat: Text.PlainText`
([`../conventions/qml.md`](../conventions/qml.md) §8.6); the bar's tooltip and
the notification daemon are somebody else's `Text`, which is why the string
itself is made safe as well. Used by `Daemon.status_state`, the pad-connected
notification and `menu.listed`.

## Do not

- Make the loop depend on the plugin being up.
- Add a request/response round trip. There is no channel back: the plugin asks
  for things by spawning `omapad ctl`, which is a separate socket and a
  separate process, precisely so a drawing problem can never stall an input
  one.
