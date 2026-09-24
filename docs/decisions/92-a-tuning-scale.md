# 92. A tuning scale, and a reading in words · ✅ Done · S

Asked for from the sofa, after the knob became a Braun
([89](89-a-braun-knob.md)): *slider'ın estetiği volume knob ve kronoya göre
geride kaldı* - the slider had fallen behind the knob and the chronograph.
Looked at on the screen beside the knob, it was four things:

- **No scale.** The knob prints a mark every five in a hundred; the slider
  printed nothing, so one value was read off one tile and guessed off the one
  beside it.
- **The value disappeared at either end.** The value's cross stood on the end
  cross at nought and at a hundred, and Brightness at 100% said so only in the
  figure at the top of the card.
- **One weight for everything.** End, stop and value were one two-pixel
  stroke at three lengths, where the ring's index is plainly the heaviest
  thing on it and its ends are batons in outline.
- **An empty card.** The line sat at the foot of a card whose middle held
  nothing.

**Built: the knob's scale, unrolled** - the same radio's tuning scale to its
bandspread knob, a printed scale along a hairline with a needle across it.
Every figure on the line is one the ring already has, rounded to whole line
weights because a straight figure lands on pixels where a turned one never
can (`travel-*.svg`, ten units a weight):

| On the ring | On the line | Weights |
|---|---|---|
| `dial-notch`, every five in a hundred | `travel-notch` | 1 × 6 |
| `dial-end`, foot open for the arc | `travel-end`, foot open for the line | 3 × 12 |
| `dial-pointer`, the index | `travel-needle`, across the line | 3 × 21 |
| - | `travel-ghost`, `travel-ghost-thin`: the needle's tail under the line where a press found the value, as wide as the figure there | 3 × 5, 1 × 5 |
| `dial-detent`, new here | `travel-detent` | 3 × 8 |

The needle hangs five weights below the line and clears an end by three above
it, so a value at either end of its range is the needle standing on the end
rather than hidden in it. How far it hangs is `Travel.qml`'s number, not a
drawing's: it is where the needle is hung rather than what it is.

**A stepped scale prints detents, and fills the ones stood on.** Its fine
graduations go; one detent per place it can stand, the end baton two thirds
as long, open-footed the same way. A detent the value has reached, and an end,
are drawn solid - *a stop is a place the value has stood on* was already the
argument for filling a stepped run in the accent, and now the figure says it
too. The stepped knob takes the same four figures (`dial-detent`,
`dial-detent-lit`, `dial-end-lit`): three notches round a list of three read
as a scale somebody forgot to finish.

`Travel.qml` draws in **two layers, one per ink, each opaque and faded once**
- `Knob.qml`'s answer, for the seam its first drawing showed. An end standing
on the line would otherwise paint their shared pixel twice.

**A reading is words now, on both surfaces.** *HUD'dakileri yazıya
çevirelim, slider olması saçma zaten.* A share the machine keeps answering
drew a slider's line under itself, on a page nothing can push, and read as a
control that had lost its thumb. The HUD tile is its name and its figure on
one line; the menu's readout tile is its heading and figure. The daemon still
sends `v` for a share - it is a fact about the reading, and the HUD is due a
rewrite that may want it - and no panel draws it.

**What went:** the cross (`travel-mark`, `travel-stop`) and with it
[65](65-one-line-three-drawings.md)'s idea that the slider is the row card's
spine turned on its side. The travel's arm - the run of bare line inside each end - went
too: the ends' outer walls are flush with the card's padding, so the scale
lines up with the words above it.

**Rejected: numbers on the scale.** The T 1000 prints them. The figure at the
top of the card already says the value, and a number printed twice is the
filled bar's fault again ([65](65-one-line-three-drawings.md)).

**The ghost was the whole needle in outline first**, and it did not survive
being looked at: *slider'ın düşme ve artma durumunda bir önceki konumunu
gösteren daha silik hali kötü bir görüntü oluşturuyor.* A second needle
crosses everything the first one does - every graduation between, and at a
hundred the end's own outline, where two outlines laid over each other read as
a smudge. It is the needle's tail alone now, hung under the line where the
value was found: nothing else is printed there, so it has that band to itself.

**And it is as wide as the figure the value was found on**: *eğer bir önceki
konum bunlarsa ... altta kalın olmalı, eğer ince bir konumdaysam ... ince
olmalı*. Three weights under an end or a detent, one under a graduation - a
stub one width everywhere said *somewhere around here*, where this one is the
foot of the very mark the value left.

**The card of rows tried it for one pass, and kept only thicker ends.** *Dikey
slider dediğim bir tasarım var, onu da uyarlar mısın* - the card
[65](65-one-line-three-drawings.md) called a vertical slider took the
slider's figures turned a quarter: an end baton at the head and foot, a detent
per row, the row in force's filled. *Kötü oldu, bir önceki tasarımın sadece
üstü ve altını daha kalın mı yapsak.* The crosses and the two strokes
bracketing the row in force came back, with a heavier cap at each end - two
weights solid, which read as a slab, then a box in outline the line stopped
against. Neither lived: *en üstteki ve en alttaki kutu yerine çizgi olsun eski
hali gibi, biraz daha uzun olabilir diğer tasarımlara uyması için.* The cap is
the old cross again, at eleven weights across where it was seven - a slider's
end is twelve, and eleven keeps the two arms equal round the line.

**And the row in force is the slider's needle laid along the line.** The two
marks bracketing it grew to one arm of the cap first, so the marks and the
caps stopped at one edge; then they went: *[ yerine daha kalın bir | mi olsa,
mevcut slider'a benzer olacak şekilde*. The row in force's length of the line
is three weights wide now, one either side, solid in the accent - one figure
where the eye had been assembling a `[` out of three. `travel-side` and
`Metrics.spine.cross` went with the marks.

**The quick menu draws the same slider.** *Quick menüdeki slider kötü ve
uyumsuz.* Its band still drew the rounded trough filling with the accent that
[65](65-one-line-three-drawings.md) retired from the menu, and beside the
menu's scale it read as another product. It draws `Travel.qml` now, with the
menu's inks written out as a mirrored measurement - continuous, and with no
ghost, because a nudge on the row writes straight through and there is no
press in progress to mark.
