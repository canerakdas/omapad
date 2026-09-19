# 63. A corner nobody could argue with · ✅ Done · S

Asked for from the sofa: *radius'u OS'e göre yap ama menüden arttırılıp
azaltılabilsin, silver ratio'ya göre bir bak.*

The first half was already true and worth saying out loud: the base is
`decoration:rounding`, the compositor's own answer about every window on this
machine, and `[menu] tile_corner` only where it rounds nothing - a desktop
that rounds nothing is saying that about *windows*, and a tile is not a
window. What was missing is the second half: nothing could move it from the
pad, and it is the one measurement you can only judge by looking at the thing
it sets.

`[ui] radius` is a **multiplier** over whichever base is in force, and it is a
multiplier rather than a number precisely because the base is never ours to
choose. 1.0 is exactly what the desktop rounds; 0 is square. `Display ▸
Corners` is the same number, set from the surface it changes - the tiles round
under the thumb moving the slider, which is why `apply_setting` pushes every
open view rather than waiting out the heartbeat.

**The silver ratio is where the third part of the ask landed.** The ladder
itself was already sound - `radius.card` and `radius.tile` are one base, one
scaled and one not, with `rung()` for anything off them - so what wanted
answering was the *stepping*. A corner is a size, every size on these surfaces
climbs by √2, and 23 pixels against 25 is not a difference anybody sees from a
sofa. So the setting walks stops rather than an amount: `0, 0.5, 0.71, 1,
1.414` - four presses end to end, each a corner you can tell from the last,
and it stops one rung above the desktop's own answer: two rungs past that a
128-pixel tile is a circle, which is a different shape rather than a rounder
corner.

- `stops` in a `CHOSEN` spec is the general shape of that, and three things
  had to learn it: `set_setting` walks the list, `setting_share` draws the bar
  by its stops (spacing them by their arithmetic bunches the bottom half of a
  ladder into the first third of the track), and the trigger sweep crosses it
  in stops rather than in the value's own range.
- **No ramp on a ladder.** The ramp exists because a pointer speed is
  thirty-eight presses end to end; six is not, and a held direction would
  cross the whole thing in the first push.
- Zero is the stop *under* the bottom rung rather than a rung: no amount of
  dividing reaches it, and square is a thing somebody may want.
- **The tile is a different tile, and the design already had it.** Asked from
  the sofa with a picture: *bunu yüzdeli değil de şöyle yapsak nasıl olur. bu
  tasarım tasarım klasöründe vardı ama hiç kullanmadın.* `Console OS
  v2.dc.html`'s Haptics cell is a caption, a word at the top of the type
  ladder, and four equal segments - and it is what a stopped control wants:
  the segments say how far along without arithmetic, which frees the line
  above them to say *which* stop. `141%` is a number you have to divide
  before it means anything, and against what? So `words` name the five
  (`Square · Barely · Slight · The desktop's · Round`) and `seg`/`at` draw the
  bar. A
  continuous number keeps its percentage and its unbroken bar.
- **And then everything else shaped like it**, asked for in the same breath:
  *benzer olanlarda da bu componenti kullan.* Which turned out to be two
  questions rather than one. **Few stops** decides the segments - `motion`
  (five) and `hold_scale` (seven) joined `radius`, while a pointer speed's
  thirty-nine places and the motor's twenty-one keep the unbroken bar, because
  a control drawn in segments has to have few enough of them to count from a
  sofa. **A place rather than an amount** decides the word: `motion` is worded
  because `Off` is the stop it exists to be able to say, and `hold_scale` is
  not, because 150% of the length a binding was written at is a quantity and
  `Slower` would say less than it does.

**What it cost to find out it worked.** `rescanPlugins` does not reach a
shared component: it walks the plugin's entry points, and `Metrics.qml` is
imported by them rather than being one. So the panels went on drawing the old
ladder with nothing in the log - nothing was wrong - and the first check said
the setting did nothing. The second said it did, on the strength of two
screenshots of two *different* pages. Both are written down in
[`conventions/qml.md`](../conventions/qml.md) §9 now: restart the shell for a
component, and compare the same page at both ends or do not claim a
difference.
