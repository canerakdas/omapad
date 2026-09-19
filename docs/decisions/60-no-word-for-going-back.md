# 60. A vocabulary with no word for going back · ✅ Done · S

[`research/console-launcher-ux.md`](../research/console-launcher-ux.md) §4.6:
*every focus move gets an audible tick; every confirm gets a distinct sound;
**cancels and back get a lower, softer one***. We had the first two and not the
third: `VOICES` was four words, and B either sounded like A or said nothing at
all.

`back` is the fifth, and the arithmetic in `assets/sounds.py` is the argument:
it is the **commit's own note and the commit's own interval inverted** - that
one bends up a fourth over its length, this one bends down the same fourth
from the same place - softer and shorter besides, because leaving is the
smaller event. A pair that shares a note and mirrors an interval is how a room
tells two presses apart without anybody having been taught which is which.

- **It ticks the motor, unlike `move`.** A press is a press, and the hands
  have no business finding out that something was cancelled by feeling
  nothing. What a motor cannot be is *lower*: it can be shorter or weaker,
  which says less happened, and only a falling pitch says *this went the other
  way*. So `say()` maps both of the words `rumble.VOCABULARY` does not hold
  onto its `tick`.
- **It follows the verb, never the surface going away.** `menu:back`,
  `menu:close`, `osk:close` and `osk:toggle` on the way out, `guide:close`, a
  control put back with B, and either kind of countdown backed out of. A row
  that ran and took the menu with it has an answer of its own, and two sounds
  for one press is one of them arguing with the other.
- It found one thing already wrong: `menu_untake` said `commit` for **both**
  ways off a control, so putting a slider back sounded exactly like keeping
  it. A is `commit` and B is `back` now, which is what those two words are.
- The fifth place a voice has to be named is `SoundBank.qml`, and it is the
  one no Python import would ever notice. `tests/test_sound.py` reads that
  list out of the QML now: a cue the bank does not load is a press that ticks
  the hands and says nothing to the room.
