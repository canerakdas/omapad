# Terminal - `omapad/terminal.py`

Is the window in front waiting at a prompt, or running something?

`ZL` + B closes the window in every application, and a terminal is the one
where closing is not always what was meant: a command still running is the
thing in front of you, and closing the window kills it along with the
scrollback that said what it had done. So the button asks first, and the
kernel already knows the answer - a pty has a **foreground process group**,
the one a `Ctrl+C` typed at that terminal is delivered to, and
`/proc/<pid>/stat` publishes it as `tpgid`.

The shell an emulator starts is the session leader of its pty, so the whole
question is one comparison: **while the shell's own process group is the
foreground one, the prompt is what is in front and there is nothing to
interrupt.**

## Surface

| Function | Answers |
|---|---|
| `job_state(pid)` | `(process group, session, foreground group)` for a pid on a tty, `None` for a process that has no controlling terminal - which is most of them |
| `busy(pid, depth=4)` | is a command running in the terminal this window belongs to? |

`busy` walks down from the focused window's pid, `[terminal] depth`
generations, and asks each process that is a session leader on a tty. It is
`False` for every window with no pty under it, which is what makes the binding
the **window layer's** rather than a profile's: a browser has nothing to
interrupt, so the same button is the plain close it has always been, and the
[guide](guide.md)'s window page - which knows nothing about profiles - stays
true.

## What a press pays for it

`busy()` runs **on the event loop**, in the press that asks it - the whole
point of the button is that it answers now - so what it costs is measured
rather than assumed:

| The window in front | /proc reads | Time |
|---|---|---|
| a terminal (`foot`, its shell and the command) | 24 | 0.12 ms |
| an editor with no children | 32 | 0.8 ms |
| Steam's own window, ten processes under it | 172 | 2.0 ms |

The cost is in **threads**, not processes: a child forked by any thread is
listed under that thread's own `children` file, so finding the children of an
86-thread process is 86 reads at 10-15 µs each. `READ_LIMIT` (256) is the
ceiling, counted in exactly those reads and charged before each one - without
it, 64 processes of 20 threads would be 15 ms on the loop, which is two ticks
of pointer movement dropped for a question about a window with no terminal in
it. A tree that wide is a browser's renderers; the answer the bound cuts short
is the close this button always gave.

Nothing here spawns a process, and nothing waits on one - the rule in
[`daemon.md`](daemon.md) is about a press that waits on a subprocess, and this
is a handful of reads from a pseudo-filesystem.

**It never raises.** An action that throws takes the loop with it, so a pid
that is nonsense, a `/proc` that says nothing and a process that ended
mid-walk are all `False` - which is the close, and the behaviour this button
had before any of this existed.

## What it cannot see, and why that is the safe direction

- A shell inside **tmux or screen** belongs to the multiplexer's session, and
  the server is not under the window at all, so a busy pane reads as idle and
  the window closes - exactly what this button did before any of this existed.
- A terminal serving several windows from **one process** (`foot --server`,
  `kitty --single-instance`) is the other way round: any busy tty under that
  pid answers for all of them, so an idle window declines to close while
  another is still compiling.

Neither can close a window over a command that is running in it, which is the
direction that costs something. A window that will not close is one press of
the same button away from closing, once the command has gone.

A background job (`sleep 100 &`) leaves the shell in the foreground and reads
as idle, which is right: a `Ctrl+C` at that prompt would not reach it either.

A window that will not close because something in it never ends is not a
window that cannot be closed: **Close window** is a row in the
[menu](menu.md), which is a chord away from anywhere, and it dispatches the
close directly.

## What it can be asked, and by whom

Everything it reads - `/proc/<pid>/stat`, `/proc/<pid>/task/*/children` - is
world-readable and read with the daemon's own uid; there is no privileged step
here and nothing to escalate. It opens no fds of the inspected process, follows
no symlinks (`handover.holders` is the one that reads `fd/`, and this is not
it), spawns nothing, and builds no path out of anything but an integer. Under
`hidepid` a process it may not read is an `OSError`, which is a `False`.

Two races, both bounded. A pid can be **recycled** between the focus event that
recorded it and the press that asks about it, and the focused window can
**change** in the same gap - so the answer can be about the wrong process. It
can only pick the wrong half, never the wrong target: the interrupt is a key
press, which goes wherever the focus is, and the close is `hl.dsp.window.close`
on the active window. Both act on the window in front at the moment of the
press, whatever the walk decided.

The two halves are ordinary actions from the config file, so `idle` can be
`exec:` anything - the same trust every binding in that file already has, and
no wider a door than the file itself.

## Where it is used

[`actions.TerminalAction`](actions.md) - `term:interrupt`, the window layer's
`B`. Both halves of what it does are settings rather than constants, because a
scheme that closes windows some other way must be able to say so without
losing the interrupt with it:

```toml
[terminal]
interrupt = "key:CTRL+C"
idle = "hypr:hl.dsp.window.close()"
depth = 4
```

They are parsed into actions **when the config loads**, so a typo is something
`omapad check` names rather than a window that will not close.

Related settings: `[terminal] interrupt`, `idle`, `depth`.
