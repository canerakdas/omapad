# 56. The first start nobody walks to a keyboard for · ✅ Done · S

The same survey, §4.10 again: *accessibility settings reachable from the
first-run flow and from the overlay.* The second half was true - motion is on
`Display`, vibration and sound on `Controller` - and the first half could not
be, because **this program had no first run at all.** It starts, it works, and
what it can do about a screen somebody reads badly or a motor somebody cannot
feel is four pages away from a person who does not yet know there is a menu.

A machine driven from a sofa is the machine nobody walks to a keyboard to set
up, so the first start has to offer what a first start decides, from the pad.
It is one tile, `Start here`, at the top of `Now`, and behind it one page: the
bindings guide, the mapping screen, vibration, sounds, motion and item 55's
hold time. Every row reads the same `pad:` setting its home row does, so this
is not a fifth place to keep them and the two cannot drift.

- **`when = ["first_run"]` is how it goes away**, which makes it the first
  state in `menu.WHEN` that nobody can point at twice. That is the rule the
  list is kept short by, and this is the one thing it is worth breaking for: a
  row true exactly once is what a first start *is*.
- **Opening the menu is what answers it**, not pressing the tile. Somebody who
  opens the menu, reads the tile and walks off has been offered the page; a
  greeting waiting to be pressed would be on the first page for ever.
- **The mark is a setting because settings.toml is the only thing the pad can
  write.** `[menu] first_run`, written false by `set_menu` rather than through
  `set_setting` - nothing to apply, nothing to repaint, and a notification
  saying a mark had been written is the machine talking about itself. Deleting
  the line brings the tile back, which the file's own header already explains.
- **It cost the suite a rule.** Opening a menu now writes a file, and
  `tests/test_kbd.py` built a real daemon without redirecting the path - so a
  test run replaced the settings this pad had chosen from the sofa. Both
  harnesses redirect it now and `test_packaging.py` fails if a third one
  forgets.
