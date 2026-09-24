# 89. A Braun knob, drawn in lines · ✅ Done · S

Asked for from the sofa, after the clock became a 6139: *Saat kadranı güzel
oldu, benzer bir estetiği volume kadranında da uygulayabilir miyiz. Günümüzde
ikonik knob tasarımlarından, minimal line drawing tarzı?* - the same aesthetic
on the volume knob, after an iconic knob. Offered three - Braun, the Nest
thermostat's ring of ticks, Teenage Engineering's flat cap - and Braun was
picked.

**Drawn from photographs of a Braun T 1000**, the lesson of
[88](88-a-6139-drawn-in-lines.md) taken first rather than on the fourth try.
Its bandspread control is the archetype: a dark cylinder with a knurled edge
and a flat top, a white index painted on the top, and a scale printed on the
panel round it - a hairline arc, a short mark every nine degrees of its three
quarters, and at each end a longer mark the arc turns into. Taken as it is,
bar the count of marks:

- **The cap.** An edge drawn as the clock's case is - two hairlines close
  together - round a plain flat top. It never turns: a drawing that rotated
  for nothing would be work every frame a thumb moves the value. The knurling between the two went, after one look at it
  on the page: *knob'da 2 daire arasındaki çizgileri kaldıralım mı?* A
  hundred and twenty ribs at tile size are no longer ribs but a grey band,
  and each one touched both circles.
- **The index**, a bar from near the cap's middle to near its edge, in the
  accent. No hub under it: it is paint on a flat top, not a hand on a pivot.
- **The printed scale**: the arc, the two longer ends, one mark per place on
  a stepped value, and on a continuous one **a mark every five in a
  hundred** - twenty-one, where the T 1000 engraves thirty-one. Drawn with
  thirty-one first; then *her 5 birim için bir çizgi olsa nasıl olur*. Five is
  the step the volume takes, so a press moves the index exactly one mark and
  the lit marks count the presses: a scale in the value's own units reads
  better than a finer one in nobody's.

What the T 1000 does not have and this keeps: **the run behind the value**,
the arc covered up to it - in the trail's tint on a continuous value and the
accent on a stepped one, as [76](76-value-a-thumb-can-turn.md) had it - and
now **the marks it has reached, lit the same way**. A volume is read from a
sofa at a glance, and a hairline index turned a few degrees is not a change
anybody sees from there.

The knob no longer shares `dial-face.svg` with the stick gauge: the gauge
keeps its three-unit band for now, and whether it follows into hairlines is
its own question - a gauge draws where a thumb is, which is a different
reading from where a value has been set.

The cap is exempt from `ShapesSitOnTheGrid` for the clock's reason: nothing
snaps the square a knob is drawn in either.

**Nothing is painted over anything**, which `Knob.qml` already claimed and the
first drawing did not keep: *iç içe geçen yerlerde kötü bir görüntü oluyor,
üst üste binmiş gibi*. The ink is the menu's text at 0.3, and translucent ink
painted twice is darker than either coat, so every place two figures met
showed as a blot. There were three. The marks began inside the scale's stroke
rather than at its edge, so each had a dark foot - they stop at the edge now.
The two ends stood on the first and last marks at the same angles - the ends
take those places now, lit by the same rule. And the run behind the value was
a second stroke over the scale - the scale is drawn from the value on only,
so the two meet end to end. The first mark no longer lights at nought either:
the run beside it is empty there.

**Drawn in the clock's weights, and only those.** The first drawing had its
own: hairlines a shade under the clock's, a mark one hairline wide, an end a
longer hairline. Beside the 6139 it was the fainter of the two - *volume
knob'u 1px çok ince duruyor line'lar, saat kadranı gibi olsun, bir standart
olsun* - because the clock is not drawn in single hairlines. Its case is two
of them close together, and its batons and hands are outlines round a body, so
at the same size it carries more ink per figure while no stroke on it is any
heavier. The knob now borrows every figure from the clock rather than
drawing its own. The cap's edge is the case, the same two rings the same gap
apart. A mark is the sweep hand's width. An end is an hour baton in outline. The index is that baton filled in, the way the accent is solid on the
clock. The arc is the clock's hairline, a quarter of a unit.
`DialsShareTheClocksWeights` checks each drawing against the clock's own
paths, so a third circle, or a redrawn clock, takes the knob with it instead
of drifting from it. The separate ring round the flat top went: a double
edge with a third ring inside it looks like a target, not a knob.

**And the arc turns into each end rather than stopping at it**: *volume
knob'unda 0 ve 100'un köşesinde kesiklik var*. With the ends drawn as
batons, the arc still stopped where it had stopped for a single hairline, at
the mark's middle. Half the baton hung past the arc's end and the two met at a
point, which read as a break at both ends of the scale. The arc now runs on
under each end, to its far side, and the baton is drawn with its foot open.
The arc closes the foot, so the scale and the baton's outer side meet as one
corner, as the T 1000's arc turns into its end marks. At either end the
overrun takes the colour of whichever run is there, so the corner is lit
together with its baton.

**Two layers, and the rule against touching retired.** Looked at closely, the
corner still had a seam: *çok yakından bakınca köşelerde renk farkı var gibi*.
The arc and the end were two figures in a translucent ink sharing an edge,
and the pixel both edges fall in gets two partial coats, which add up to less
than one. The rule that nothing is painted over anything had been answering
half of that problem: it stopped the blot an overlap makes and caused the
seam an edge makes. The knob is now drawn as two layers, one per ink - what
the value has not reached, in the dial's ink, and what it has covered, in the
run's - each painted opaque and faded once as a whole. Inside a layer the
figures overlap where they meet: a mark's foot stands in the arc to its
middle, an end's to its inner edge, and the arc ends under the end's outer
side. The two layers meet only at the value, and the run reaches half a mark
past it, so a lit mark's foot never stands on the unlit scale. The price is
two textures the size of the face per knob, drawn again when the value
moves.
