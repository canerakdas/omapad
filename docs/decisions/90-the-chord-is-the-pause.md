# 90. The chord is the pause · ✅ Done · S

Asked for from the sofa: *quick menude workspace lock ve keep gamepad olmali en
cok kullanilan featurelardan biri bu maalesef* - the workspace lock and keeping
the controller belong on the quick menu, since they are among the most used
things there are. Then, on hearing how the row is reached under the lock:
*minus + plus'in quick menu acmasi gerekmiyor mu menu yerine* - shouldn't
MINUS + PLUS open the quick menu rather than the controller menu?

**The two tiles went on the row, straight after Resume.** They had been on
`Spaces` since [86](86-now-given-out.md), which is a chip along the bar and a
walk down the grid - a page away from a game somebody is pausing. The row's
`when` could only say `window` or `empty`, so it grew the menu's states
(`game`, `handed_over`, `locked`, `kept`; not `first_run`, which the menu spends
by opening). A place listed beside them still has to hold: the lock is
`["window", "game", "handed_over"]`, since over an empty workspace it locks the
pad to nothing. Neither tile has `stay`: picking one ends the pause.

**And the chord was the door to the wrong menu.** It opened the controller menu
from [36](36-cloud-session-menu.md), when nothing else reached past a game.
[85](85-two-menus-two-buttons.md) gave the menu HOME, and HOME reaches past a
game on its own - so over a game the chord was a second way to the menu, and
the row had none except the chord and then PLUS inside the menu. Under the
workspace lock, where only a chord gets through, the tile somebody wanted was
two presses and a page away.

So `"MINUS+PLUS" = "quick:open"`: the chord is PLUS for where PLUS belongs to
the game. The controller menu is still one step past it - Y on the row, or its
Menu tile - and still HOME over a game that is not locked. The lock's
notification says *the quick menu* now.

`open`, not `toggle`. PLUS acts on the way down, so with PLUS landing first the
row is already up when MINUS completes the chord; a toggle there shut it again.

**Then the row was pruned to a call.** *quick menude parlaklik, screenshot,
record olmasin mic mute ve deafen olsun discord gibi* - no brightness,
screenshot or record on the row; mic mute and deafen instead, like Discord.
Brightness is still on `Display` and the screenshot is still Capture; what a
pause over a game is for, on this sofa, is the call running beside it.

So two new `live:` switches, `mic` and `deafen`, and a tile each after
Volume, both `stay` so they light where they are pressed. They are the
machine's microphone and speakers rather than Discord's keys: over a game
Discord is not in front, and a key would reach the game. Deafen is on while
both are muted, so muting the speakers from `Sound` does not light it; off
unmutes both, where Discord puts the microphone back to what it was - that
takes a memory a reading does not keep. A write to one re-asks the other
(`touches`), or the Microphone tile goes on saying unmuted after a deafen.

**And they say so.** *deafen ve mute icin bir ses ekle, uygunsa mevcut sesler
de olur* - a sound for deafen and mute, existing ones if they fit. They fit:
muting says `back`, unmuting says `commit` - one falls and one rises, which is
what Discord's two sounds do, and a new voice is five files for a distinction
the pair already makes. The catch is that the cue plays through the speakers a
deafen mutes, so that mute waits `QUIET_AFTER` (150 ms) for its cue and the
unmute is said only once the helper has answered. The Sound page's Mute
switch gets the same, since the rule is the reading's and not the tile's.

**Rejected:**

- **Letting PLUS alone through while locked.** PLUS is the game's own pause
  button, and the lock exists so that nothing of ours lands over a game.
- **A second chord for the row**, leaving MINUS + PLUS on the menu. A chord is
  two buttons a game never asks for, and there are few of them; spending one on
  what HOME already reaches over a game is a door twice over.
