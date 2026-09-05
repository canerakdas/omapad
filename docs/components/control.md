# Control socket - `omapad/control.py`

A unix socket at `$XDG_RUNTIME_DIR/omapad/control.sock` (`[control] socket`),
so the daemon can be driven without the pad:

```bash
omapad ctl osk toggle
omapad ctl mode game
omapad ctl lock toggle
omapad ctl press A
omapad ctl status
```

The path comes from [`paths.socket_path`](paths.md) unless the config names
one: `press A` runs whatever that button is bound to, up to any `exec:`, and
nothing on the socket is authenticated, so the directory it sits in - per-user
and 0700 - is what stands in for that.

It exists for three cases: a Hyprland keybind that summons a surface, a script,
and a pad that has gone flat mid-menu. `Surfaces.qml` uses it too - the shell's
summon lands on `omapad ctl <verb> open` rather than on the panel opening
itself, because surface state lives in the daemon.

## Shape

`ControlServer` is a listening socket with a `fileno()`, so the daemon
registers it with `poll()` like any other fd. `serve(dispatch)` accepts one
connection, reads one line, hands the words to the daemon's
`handle_control()`, writes the reply back and closes.

One request per connection, no protocol beyond words and a line: a control
socket that needed a client library would be a worse `hyprctl`.

## `press <BUTTON> [tap|hold]`

A button fired from somewhere that is not the pad. `tap` (the default) replays
a press and a release through `handle_button()`, so the chords, the layers and
the tap/hold timing decide it exactly as they would for a thumb; `hold` fires
the other half outright, for a binding that only has one.

The button is named in omapad's own logical names - `R`, not the `RB` an
Xbox pad prints - because a badge's printing is the guide's question and
changes with the pad. An unknown name is answered, not ignored.

This is where a click on a game-bar badge lands: the panel knows what a badge
prints and nothing about what it does, so it sends the name back and the daemon
answers with the same binding a press would find.

## Rules

- **The socket is optional.** It failing to bind is a log line, not a startup
  failure.
- Every verb `ctl` accepts is also something a binding can do through an
  action; the socket is a second door onto the same room, never the only one.
- `handle_control` returns text a human can read, because a person is usually
  the one typing it.
