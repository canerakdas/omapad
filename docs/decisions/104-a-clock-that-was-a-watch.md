# 104. A clock that was a watch · ✅ Done · S

Asked for from the sofa: *stopwatch saatini kaldiralim tile dursun kuculunce
ortaya dijital alma olayini da kaldiralim, saat proje ile alakasiz duruyor cok
ugrasmis olsak da* - take the watch off the stopwatch and keep the tile, drop
the figures it falls back to in the middle when small, because the watch
looks unrelated to the project, however much went into it. Asked which faces
that meant, the answer was all of them: the clock's as well.

**What the problem turned out to be.** Four decisions built one drawing: an
analog face ([74](74-clock-read-from-the-sofa.md)), a stopwatch set into it
([75](75-clock-that-could-measure.md)), batons redrawn from a watch
([84](84-dial-redrawn-from-a-watch.md)), and the whole dial redrawn as a line
drawing of one particular watch, with figures in its place under 140 pixels
([88](88-a-6139-drawn-in-lines.md)). Each step made it a better watch, and
that was the trouble: every other drawing on these surfaces is about the pad
or the desktop - a dial is a stick, a knob is a value, a travel is a setting -
and this one was about a wrist. The two tiles it sat on were already a name
and a figure underneath it; the face was the one thing on the page that said
something else.

**What was built.**

- **Both tiles drawn the way a reading is**: the name, and the figure beside
  it. The clock's figure is the time in `%H:%M`, the head's own shipped
  format, sent as `t` - the field a reading's figure rides in - from
  `menu.time_of_day()`, which replaces `minute_of_day()` and the `mn` field.
  The stopwatch's figure is the measurement, spelled in the panel as before.
- **The stopwatch still works.** `chrono.py`, the pusher on A, the legend's
  `Start` / `Stop` / `Reset` and the minute's tick are unchanged; the minute
  mark is now just the minute rather than the sweep hand coming round, and
  `SWEEP` is `MINUTE`. What counted on between payloads moved out of
  `Clock.qml` into `Menu.qml` - one stamp and one timer for the surface,
  which is what one stopwatch always was.
- **A reading's room**: `clock` and `chrono` are two cells by one at least.
  The shipped stopwatch keeps `span = [2, 2]` so the band it shares with the
  pairing tile on `System` stays full.
- **Gone**: `Clock.qml`, the eight `clock-*.svg` shapes and their entries in
  `ControlArt.qml`, the HUD's `ControlArt`, and the figures-when-small
  fallback. The knob was drawn in the watch's weights and tested against its
  files (`DialsShareTheClocksWeights`); it keeps the same weights, and
  `KnobFiguresAreOneBaton` now holds its end, index and detents to each other
  instead.

**What was rejected.** Keeping the clock's face and removing only the
stopwatch's: the question was which drawing belonged, and the clock's face was
the same dial. Printing the figure large in the middle of the tile: that was
the fallback asked out, at every size.

**What it cost.** Nothing in a config: `control = "clock"` and `"chrono"`
mean what they did, and a `span` written for the old square still fits - it
is a larger tile with the same line at its head.
