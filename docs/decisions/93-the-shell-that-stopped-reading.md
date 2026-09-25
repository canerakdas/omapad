# 93. The shell that stopped reading · ✅ Done · S

Asked for from the sofa: *inputlarda bir gecikme var mı* - is there a delay on
the inputs - checked element by element before anything was changed.

**The daemon was never the slow part.** Built with the suite's recorders in
place of the sockets, a press costs it well under a millisecond on every
surface: 0.28 ms on the menu, 0.18 on the keyboard and the game bar, 0.07 on
the quick menu, 0.03 on the guide. The pointer is one tick at `poll_hz`.
Nothing there was worth touching.

**The desktop was.** `omapad budget stress` against the running daemon put a
median of one or two milliseconds on every surface's commands, and a worst
case of 300 to 510 ms on every one of them. The worst cases were one number
over and over, 501, 504, 507, 513, and the only half-second in the tree was
`ViewClient`'s socket timeout. Sampling `ss` through the same run showed
why: **every omapad socket sat unread at once, for 0.3 to 1.2 seconds**,
around a surface opening. Quickshell is one thread for every panel it draws,
and while it builds one it reads nothing.

A blocking `sendall` turned that into two faults at once. The loop waited the
whole half-second - the pad answered nothing, whatever was pressed - and then
the timeout closed the socket and dropped the line, so the panel kept drawing
the old state until the next heartbeat, two seconds on. A press that seemed
to do nothing, and then seemed to have done it late, was both of them.

The same pass found a smaller one: **the keyboard shelled out on the loop at
every opening.** `xkb.active_layout()` spawned `hyprctl devices -j` (8 to 20
ms here, three seconds of timeout while the compositor was busy) and a new
layout compiled `xkbcli` on the loop behind it (five). `daemon.md` already
said nothing on the loop may spawn `hyprctl`; this was the one place still
doing it.

## Built

- **A view socket that never waits.** Non-blocking, connect included. What
  the shell will not take waits in the client, and only the newest of it:
  every line is the whole surface, so one that has been overtaken is one
  nobody needs. A line the socket took half of is finished first, so the
  panel never reads a torn one. The menu's gauge line says less than the
  surface, so it goes as `whole=False` and waits *behind* the last whole line
  rather than in its place. See [viewsock](../components/viewsock.md).
- **The loop offers it again.** `flush_views()` after every pass's events,
  and `views_waiting()` holding the poll at frame rate while anything waits,
  so a panel that was busy being built draws the present the moment it is
  back rather than a heartbeat later. A stall of a tenth of a second or more
  says so in the journal when it ends, which is the measurement the next
  item on the roadmap starts from.
- **The layout over IPC, the compile in the worker.** `active_layout(devices)`
  reads `j/devices` from the socket the daemon already talks to;
  `compile_command()` is the `xkbcli` line the worker runs. The keyboard
  opens on the labels it had and repaints when the table lands, and `start()`
  compiles the first layout so the first opening already prints it. See
  [xkb](../components/xkb.md).

## Rejected

- **Watching the view sockets for `POLLOUT`.** The obvious way to learn the
  shell is reading again, and wrong here: `poll` registers by number, a view
  socket that closes gives its number straight back, and the next keyboard
  or control connection to take it is something this poller already watches
  for `POLLIN`. Unregistering the dead one would unregister the live one. A
  flush on every pass costs ten attribute reads and has no such number to
  hold.
- **A longer timeout, or a shorter one.** Either is still the loop waiting
  on a panel, which is the thing [viewsock](../components/viewsock.md) says
  it must never do.
- **Turning off the compositor's fade on omapad's layers.** Hyprland fades a
  new layer in over 179 ms on top of the panels' own 90-110 ms, and a
  `noanim` layer rule would win that back. Weighed and left: it is a line in
  somebody's compositor config for a cost that is the desktop's own taste,
  and [91](91-what-the-desktop-gave-up.md) is this project deciding not to
  ask the compositor for things.

## Then the page turn, and a trigger that was not free

Asked next from the sofa: LB/RB on the menu stuttered. Measured with the
shell's own socket as the clock - a byte every 20 ms into `status.sock`, and
`ss` watching how long it sat unread - **every page turn froze the shell 110
to 215 ms**, at the turn, longer than the 110 ms slide it swallowed. The tile
delegate in `Menu.qml` built every kind's drawing on every tile and hid what
it was not: a `Knob` and a `Clock` in every tile's middle, a `Travel` at every
foot, two words on every switch plate. A page is every tile built again.

**Built:** the ring, the clock and the travel behind `Loader`s whose `active`
is their kind, and the plate's repeater empty on a tile that does not switch
([qml.md 5.6](../conventions/qml.md)). The same ten turns, warm: **13 to 94
ms, a median of about 47**, down from about 160. The pages were checked on
screen - the ring, a slider, a clock and the stopwatch's figures, which the
head line reads through `clockLoader.item`.

The same pass found LT doing two things on the menu. The triggers are the
menu's sweep, read as axes, and `MENU_TRIGGERS` said that left both free
because a surface layer falls through to nothing. ZL's button is the window
layer's trigger, though, and a trigger is not a binding: every pull opened
the window layer under the card, and while it was held the left stick resized
the window behind and the D-pad walked its focus. `surface_override` now gives
both triggers to the menu and to the quick menu (`TRIGGERS_KEPT`), which had
the same fault with nothing to sweep. What it costs is the window layer over
those two surfaces, which a held modifier reached until now; the card is over
what it would have moved.

## And the four it left

Taken the next day, in the order the roadmap had them.

- **The shell freezing for 0.3 to 1.2 s at a surface opening** did not come
  back. With the tiles no longer building every kind, a shell restarted
  seconds earlier froze 10 to 49 ms at the first opening of each surface and
  4 to 31 at the second. The second-long freezes were `budget stress`'s own
  first second, a burst no hand makes. Memory is what is left to watch:
  selection churn at 30 ms a command left the quick menu 36 MB and the guide
  16 over forty cycles, nothing at a thumb's pace.
- **The rest of a page turn** was measured part by part and left at 17 to
  37 ms: the row stack builds nothing off a card, and the halo, sheen and hit
  shapes left out altogether bought 4 ms, inside the noise.
- **The keyboards on the desk** are let go of on a thread (`close_aside`):
  3 to 11 ms a node of RCU grace period that every surface closing used to
  pay on the loop. The slowest tenth of `budget stress` fell from 8-12 ms to
  2-5.
- **`budget` sees the shell now**: `ShellWatch` times it from the bar
  widget's socket (`TIOCOUTQ` on a knock every 20 ms), `budget stress` prints
  a `stalls:` line, and `budget pages` times every menu page turn.
