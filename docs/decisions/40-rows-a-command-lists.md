# 40. The television's two devices, and the rows nobody could write down · ✅ Done · M

Asked for from the sofa: *when I plug the television in I should be able to
pick the sound and the microphone, or it is back to a keyboard and a mouse.*
Which is exactly right, and the reason it had never been a row is that **the
answer is not in a config file**. A menu built at load can only name what was
written down; plugging a television in adds an output that was not there when
anybody wrote anything.

**So a row can list its own submenu.** `from` is a command, `action` is the
template each of its lines runs, and the line carries the values as `%1` and
`%2` - a node id and a device name, because the command that moves the sound
wants both. Read when the row is entered rather than cached, since the whole
point is that the answer moves; the OSK page a profile lends an app (32) had
already established that a command's output can be a surface's content, and
this is the same idea one surface along.

**The tick is the feature.** `state(action)` can ask a setting what it holds,
but nothing can ask a device whether the sound is going to it - so the listing
says. A label that arrives with a `*` is the one in force, which is the mark
`pactl` and `wpctl` already print beside the current device, and the mark is
not drawn. Without it the page would be three names and a guess. Picking a row
moves the tick locally and keeps the menu up: the command is let go of rather
than waited for, so re-reading the listing at that moment would race the thing
the press has only just started, and the answer settles at the next entry.

**Every value is quoted as it goes in**, and that is not tidiness. A device
names itself from its own USB descriptor - from outside this machine - and the
name lands in `/bin/sh -c`. A speaker called `x; rm -rf ~` is a plausible
thing to hand a daemon that runs as the user.

**The two listings are not symmetric, and the second one was wrong first.**
The outputs are the ones Omarchy's own switcher offers: a sink whose only ports
are unplugged is left out, and so is the physical sink a speaker tuning fronts.
Copying that filter onto the inputs listed *nothing at all* - a built-in
microphone reports its jack as unplugged and is still the microphone in use, so
the filter hid the row that was ticked. The inputs are every source that is not
a monitor instead, a monitor being what the speakers are already playing rather
than anything anybody speaks into.

**A press no longer waits for the command.** It did at first, which was the one
thing here that broke the loop's own rule, and `[menu] list_timeout_ms` was all
that stood between a wedged listing and a pad that had stopped answering. The
honest version was written afterwards: `actions.Commands` runs the command on a
thread, the press enters the page at once, and the rows land in it when the
answer does. The timeout is still there, now as the floor under the thread.

**They are a page of their own, and that was the second thing asked for.**
Beside `Mute` and `Play / pause` the two rows read as an odd third thing, and
the complaint named it exactly: the Audio submenu was answering *how loud*,
*where the sound goes* and *what is playing* in one column. Only the middle one
is set when the room changes rather than while you are sitting in it, so it
goes a level down under `Devices` - the rule the menu already follows, that
what a thumb reaches for often keeps the top of the page.

**Found on the way:** the menu card is a fixed width, so a long device
description elides. Left alone. It elides from the right, which is where the
part that distinguishes one device from another is not, and widening the card
for this would be the menu no longer measuring the same as the Omarchy one.
