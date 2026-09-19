# 79. Four words that never changed · ✅ Done · S

Asked for from the sofa: *menudeki bir kartin ustune gelince sag alttaki
butonlar cok anlamsiz surekli ayni sey yaziyor gibi, b ve x varsayilan olarak
cikma egilimi, a'da klavyede pick yazmasi ne alaka, previous'da da pick
yaziyor previous yazmasi gerekmez mi, volume icin knobda left right arrow ve
left stick cikmasi lazim bence.*

Every clause of that is one fault. The legend was **page-scoped**, and a page
is not what a thumb is standing on: `Pick`, `Back`, `Close`, `Arrange` stood
under the keyboard tile, under `Previous`, under the volume ring and under a
stopwatch, unchanged all the way across the page. Three exceptions had already
been carved out of it - the chronograph's pusher, `Hold to confirm`, `Cancel`
under a count - which is the shape of a rule that wants inverting rather than
three special cases.

- **A asks the tile.** `menu_verb()` reads `acting`, the same property a press
  acts on, so the word and the press cannot be about two different things. A
  row that runs something says **its own label** - `Keyboard`, `Previous`,
  `All apps`; a page says `Open`; a bar or a ring says `Adjust`, and `Keep`
  once it is held; a switch says which way it is about to go; the transport
  says `Play` or `Pause`. The three exceptions are now three rows of that
  table rather than three branches in the loop.
- **Deriving the verb from the action was tried first and is wrong.**
  `guide.brief_of` is what the game bar reads a binding with, and pointed at
  `live:media=previous` it prints `live:media=previous`: `live:` has no
  describer, and it would need one per row a config file can invent.
  `exec:omarchy-menu toggle apps` reads no better - it comes back as `Menu`.
  The label is the interface's answer to *what happens if I press this*,
  already written to `writing.md`'s budget, and it is under the thumb. That is
  now rule 13 there.
- **A press that does nothing gets no row.** A reading is published rather
  than set, a clock is not a button, a card that lists one thing is furniture
  round a fact, and a row already counting down refuses a second press. The
  strip is what somebody checks *before* pressing, so an A on any of those is
  worse than a strip one row shorter.
- **B says what it is leaving**, which is the `b ve x` half of it. `Cancel`
  over a value pushed too far or a count, `Back` inside a page, `Close` at the
  top of a group - where `back()` answers False because the bar is not a level
  to climb to. And there X stands down: it is `menu:close`, so it was printing
  B's own answer a second time under a second badge. Inside a submenu they
  part company again and both are printed.
- **The directions arrive when they mean something.** Take a control and the
  strip gains `◀ Less` and `▶ More` - `Previous` / `Next` where the control
  reads a choice - and on a knob the left stick, which is the one control the
  stick does something else with. Not before: until A takes hold, left and
  right walk the page, so printing them beside a value nobody is holding would
  be this row's one job done backwards.

**What it cost to draw: nothing.** `LegendBadge` already asks `ButtonArt` for
a kind and a label, and the D-pad and the stick have been in the generated art
since the guide first printed them - so the two arrows and the ring's stick
are rows on an existing wire with an existing drawing. The payload did not
change shape either: it is still `{b, k, n}` per row, and the panel still
draws whatever it is sent.

**The one shipped page, walked tile by tile**, is what the review asked for
and is in `MenuLegendTests`. `Now` now reads `A Keyboard`, `A Play`,
`A Adjust`, `A Previous`, `A Turn on`, `A Start` as the thumb crosses it,
against `A Pick` six times before.
