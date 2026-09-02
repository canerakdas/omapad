# View socket - `omapad/viewsock.py`

58 lines, and one of the two load-bearing boundaries in the project.

## The contract

The daemon connects, as a client, to a socket the **plugin** listens on:
`$XDG_RUNTIME_DIR/omapad/<surface>.sock`. It pushes one JSON object per
line, one line per state change, and re-sends everything every
`VIEW_HEARTBEAT` seconds.

```
osk.sock  menu.sock  guide.sock  mapping.sock  gamebar.sock  status.sock
```

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
  push is the whole surface, so a heartbeat and a press both hand the panel a
  great deal it already has. Sending a diff instead would cost the heartbeat
  its one job, so the filtering is on the drawing side: see
  [`../conventions/qml.md`](../conventions/qml.md) §5.4. Adding a field here
  needs nothing of the panel beyond a `fresh()` guard if it is a model.

## Payload rules

See [`../conventions/data.md`](../conventions/data.md). In short: field names
are short and stable, every field is optional and additive, and everything the
plugin needs - including the surface scale and the bar's own proportions - is
in the payload, because the plugin cannot read the config.

## Do not

- Make the loop depend on the plugin being up.
- Add a request/response round trip. There is no channel back: the plugin asks
  for things by spawning `omapad ctl`, which is a separate socket and a
  separate process, precisely so a drawing problem can never stall an input
  one.
