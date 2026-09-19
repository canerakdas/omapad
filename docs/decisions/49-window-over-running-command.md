# 49. The window that closed over a running command · ✅ Done · S

*game modda terminalde lt+b pencereyi kapatmak yerine ctrl+c yapsa kapatilacak
bir sey yoksa pencereyi kapatsa gibi bir ozellik ekleyebilir miyiz*.

`ZL` + B closes the window in every application, and a terminal is the one
where closing is not always what was meant. A command still running is the
thing in front of you; closing the window kills it and takes the scrollback
that said what it had done with it. Item 37 had already ruled the interrupt
onto `Y`'s hold, and this is the other half of the same question - not where
`Ctrl+C` lives, but what the close should do when there is something to
interrupt.

**Asked from /proc, not guessed at.** A pty has a foreground process group -
the one a `Ctrl+C` typed at that terminal is delivered to - and
`/proc/<pid>/stat` publishes it as `tpgid`. The shell an emulator starts is the
session leader of that pty, so the whole question is one comparison: while the
shell's own process group is the foreground one, the prompt is what is in
front. `omapad/terminal.py` walks down from the focused window's pid and asks
each session leader it finds. Measured against both terminals open on this
machine while they ran a command, before it was believed.

**It stayed in `[bindings.window]` rather than becoming the first
`[profile.shell.window]`.** `busy()` answers False for every window with no pty
under it, so a browser, a game and a file manager all take the plain close -
and the guide's window page, which knows nothing about profiles, goes on
telling the truth. The `desc` grew the second half it now has: *Close the
window, or the command in it*.

**Both halves are settings.** `[terminal] interrupt` and `idle` are parsed at
load like any other action, so a scheme that closes windows some other way
changes a setting rather than losing the interrupt with the close, and a shell
driven with something other than `Ctrl+C` says so. `depth` is how far below the
window to look for the shell; every emulator measured here starts it as a
direct child.

**Asked for in game mode, shipped in both.** Game mode is the couch
environment, not a shorter desktop: a window layer that behaved differently in
the two would be a second scheme to learn. What the item is really about is the
couch, where the window that will not close is harder to explain than anywhere
else.

**What a press pays for it, measured rather than assumed.** The walk is on the
event loop, because a button has to answer now. A terminal's whole tree is 24
/proc reads and 0.12 ms; Steam's window, ten processes under it, is 172 and
2 ms. The cost is in threads rather than processes - a child forked by any
thread is listed under that thread's own `children` file - so the bound is
counted in those reads: `READ_LIMIT`, 256, charged before each one. Without it
a browser's renderers would be 15 ms on the loop, two ticks of pointer movement
dropped for a question about a window with no terminal in it. And `busy()`
never raises: an action that throws takes the loop with it, so a nonsense pid,
an unreadable /proc and a process that ended mid-walk are all False, which is
the close.

**What it can be asked, and by whom.** Everything it reads is world-readable
and read with the daemon's own uid - no privileged step, no fd of the inspected
process opened, no symlink followed, nothing spawned, and no path built out of
anything but an integer. Two races, both bounded: a pid can be recycled and the
focus can move between the event that recorded it and the press that asks. Both
can only pick the wrong *half* - the interrupt is a key, which goes wherever the
focus is, and the close is `hl.dsp.window.close` on the active window, so
neither can act on a window that is not the one in front.

**What it cannot see, and why that direction is the safe one.** A shell inside
tmux belongs to the multiplexer's session and its server is not under the
window at all, so a busy pane reads as idle and the window closes - exactly
what this button did before. A terminal serving several windows from one
process (`foot --server`) is the other way round: any busy tty under that pid
answers for all of them, so an idle window declines to close while another is
compiling. Neither can close a window over a running command, which is the
mistake worth avoiding; the other costs one more press of the same button.
