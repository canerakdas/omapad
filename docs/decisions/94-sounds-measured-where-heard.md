# 94. Sounds measured where they are heard · ✅ Done · S

Asked from the sofa: *ui sesleri bir standarda uygun mu* - do the UI sounds
follow a standard, or were they made up? The screens were built against what
the best consoles do; the sounds were five good guesses.

**There is no one standard for a UI sound**, the way XAG is one for contrast.
What there is comes in four layers, and the set was held against each:

| Layer | The reference | What it found |
|---|---|---|
| Vocabulary | Xbox's `ElementSoundPlayer`: Focus, Invoke, Show, Hide, MoveNext, MovePrevious, GoBack - the one console sound vocabulary that is written down, and the reason [`research/console-launcher-ux.md`](../research/console-launcher-ux.md) §4.6 can say Xbox turns control sounds on | `move`, `commit`, `back` were Focus, Invoke and GoBack. **Show had nothing**, and a page turned was a `move`, which said a page went and not which way. `edge` is one of ours with no Xbox word - kept |
| Design | Brewster, Wright and Edwards (1995), the experimentally derived rules for earcons: a family shares a timbre, its members differ in pitch and contour, relative pitch beats absolute | Met already - the fifth between move and commit, the mirrored fourth between commit and back. The one miss is timbre: two or three sines is thinner than they recommend, which is what a pack is for |
| Level | ITU-R BS.1770 (LUFS), with ISO 226's reminder that a low note and a high one at the same peak are not the same loudness | **Missed.** Each voice was a share of a peak. Measured, `back` was louder than the `tick` `sound.VOICES` says it costs less than, and through a television's drivers `edge` - the low one - read as quiet as the tick it is meant to stand over |
| Access | XAG 103 and 105, ISO 9241-171: never the only channel, off on its own, a volume of its own | Met - the screen and the motor say every word too, and `[sound] enabled` and `volume` are their own settings |

## Built

- **A loudness per voice, not a share of a peak.** `assets/sounds.py` carries
  BS.1770's K-weighting, written out because this tree takes no library, and
  measures a cue over one 400 ms block **through a television**: a
  fourth-order high-pass at 200 Hz for a set's own drivers. `render()` scales
  each voice to its `lufs`. They rise in `VOICES` order, two apart at the
  least. The meter is checked against the standard's own coefficients at
  48 kHz and its -3.01 check tone, and against `ffmpeg`'s `ebur128` by hand
  (within 0.1 LU on every file).
- **`edge` holds its level with harmonics, not with volume.** Scaled on its
  fundamental alone it had to become the loudest thing on a desk before a set
  heard it at all. Its own octave and fifth are strong now: a set plays the
  octave, the ear rebuilds the fundamental from it, and nothing above 350 Hz
  keeps it dull. A test says no voice loses more than 5 LU on the set.
- **`show`**, Xbox's Show. `back` upside down: A rising to D, the fourth
  `back` falls, with a slow attack so it swells rather than strikes - which is
  what keeps it from being a second commit. Said by the verb (`open`, or
  `toggle` from down) on the menu, the quick menu, the guide and the keyboard,
  never by a surface arriving by itself, so the keyboard that opens under a
  text field (30) stays silent. It ticks the hands, for `back`'s reason (60).
- **`next` and `prev`**, MoveNext and MovePrevious: the move's note bent a
  tone up or down, on the menu's bar, the guide's pages and the keyboard's
  pages - the last of which said nothing at all before. One level between
  them, because they are one gesture. Heard and never felt: `sound.UNFELT`
  names them with `move`, and `say()` reads it, because a held shoulder turns
  page after page.
- **`--measure DIR`** reads a pack of your own the same way and prints the
  gain each file needs to stand where the voice it replaces stands.

## Not built

- **Panning `move` by where the focus is.** Fluent pans its focus sound
  across the stereo field by the element's position. `sounds.py` is mono on
  purpose - *none of these happened anywhere* - and that is true of a commit
  and false of a move, which happens exactly where the ring is. It would be a
  mono file panned by the panel, not a new file, and it is a decision about
  what a cue is before it is any work. On [`../roadmap.md`](../roadmap.md).
- **A separate `hide`.** `back` already is Xbox's Hide for every surface put
  away, and a second word for the same press would be two sounds arguing.

**Not yet heard on the set.** Everything above is measured and tested; none
of it has been listened to across the room on the television it was measured
for, and that is the check still owed.
