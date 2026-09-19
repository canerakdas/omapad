# 65. One line, and three drawings of it · ✅ Done · S

Said from the sofa, reading item 64's card back: *button labels için yaptığımız
tasarım aslında dikey slider gibi, mevcut kademeli slider ve slider'ı da benzer
bir tasarıma geçirebilir miyiz.* It is the right reading of the drawing. A card
of rows is a two-pixel line with the row in force lit along its own length and
a wedge leaving it - which is a vertical slider, and the card next to it drew
its actual slider as a rounded eight-pixel trough with a fill running along it.

So there were three drawings of *where along something a number is*: the
trough, the trough cut into segments for a stepped value (63), and the spine.
There is one now. `shell-plugin/Travel.qml` is the line, drawn along the foot
of a slider, a stepped slider and a reading in the menu, and under a reading on
the HUD - which had its own copy of the trough, for the rule that a page of
readings must read the same in both places it appears.

- **The measurements moved to the ladder.** `metrics.spine` holds the five -
  the weight, how far the line carries past what it measures, the cross's reach
  either side, and the mark's reach out of the line and its base on it - and
  both the row card and the travel read them from there. Two copies of a stroke
  weight is how one drawing quietly becomes two.
- **Nothing fills**, which was the question asked back with three pictures and
  answered by picking the quietest: a bar filled to the value draws a number as
  mass, and the figure at the top of the card has already said it in words.
  What is drawn is where the value *is* - the line's own length there, in the
  accent, with the wedge over it. A stop is a length of line, so standing on
  one lights the whole of it; a continuous value lights the mark's own base.
- **It reverses half of 63.** The segments were chosen so *how far along* could
  be read without arithmetic; it is read off the mark's place between the
  crosses now, which is quieter. The trade was made with the picture in front
  of us and it buys one drawing where there were three. `seg` and `at` on the
  payload are untouched - how a value is drawn was always the panel's.
- **The stops are the cap repeated.** A cross at the end of a line says the
  line ends here; a cross partway along says it about a place the value may
  stand. The two controls then differ by exactly what the two controls differ
  by, and the ends of the line are values - a slider at its minimum stands on
  the cross, where a spine would have carried on past the last row.
- **`metrics.time.fill` went with the troughs**, and `qml.md` is down to three
  durations. A mark is where the value is rather than a length growing towards
  it, so it lands on the frame the value changes - which is 8.2.4.1, the rule
  the filling bar was the exception to.

**The crossings were wrong on the first pass**, and the sofa said so at a
glance: *dikey ve yatay çizgiler iç içe geçmiş görünüyor.* Each cross was one
bar run through the line, so the pixel where the two met was painted twice -
and every ink here is the theme's own at a share of itself, which makes a
square painted twice a square painted brighter. Seven of those along a stepped
control and the drawing reads as two strokes laid over one another. It is the
rule the row card's caps have carried since they were drawn; the travel now
carries it too, with the line taking the crossing and the arms starting above
and below it.

**And the plain line did not show a press**, said as soon as the crossings
were fixed: *kullanıcı düz çizgi olan versiyonda değişimi görebilmeli.* True,
and it is the cost of the quietest of the three treatments - a press moves the
mark a few pixels, and on a continuous slider there was nothing else on the
line to see move. The stepped one never had the problem: a whole stop lights.

So the line **behind** the value is drawn in the accent at half. It is the old
bar's length at one twentieth of its ink - a tint rather than a fill, which is
what qml.md 8.1 asks for everywhere the accent is not carrying a solid - and
the full accent still marks one place. Three strengths were rendered side by
side to pick it: a fifth (this surface's tint for a lit ground) is not there at
all on a two-pixel line, and the ink at its dim level makes the trail the
brightest thing on the card, which puts the eye behind the value instead of on
it.

What that buys back is item 63's own argument, which the first pass had spent:
the segments were chosen so *how far along* could be read without arithmetic,
and a trail running to the stop you are on reads exactly that - on both kinds
of slider and on a reading, in one drawing.

**And then the lit line crossed them too**, which is the same fault one layer
up: *düz sliderda aktif olan sol yatay çizgi ile dikey çizgi yine iç içe
geçti.* Splitting each cross into two arms had fixed the ink and not the
figure - whatever the value lights runs through every stop it has passed, so a
blue line and a grey bar still read as two strokes laid over one another. The
stops **hang under the line** now, one tick each, as long as the spine carries
past the last row of the card next door. Nothing on the drawing overlaps
anything: wedge above, ticks below, and one unbroken line between them.

**And the mark stopped being a wedge**, which is the third thing the screen
said and the clearest of them: *yatay sliderlarda ok gibi olmasın, kalın çizgi
gibi olsun, sol ve sağındaki üçgenleri kaldır.* The wedge is the row card's own
mark, and turned a quarter it is an arrow lying on the line - an arrow points
somewhere, and beside a horizontal line there is nothing to point at. The mark
is the line **thickened** now: as tall as the wedge reached, half again as long
as that, its foot on the line. At the wedge's own width it was as wide as it
was tall, and a square standing on a line is a knob rather than a length of it.

**And the two drawings settled on one stroke**, which is where the passes
above were heading: *yatay ve dikey için tüm çizgileri aynı yapalım, --+-- gibi
olsun, üstte ve altta aynı; kalınlık bardaki en sol ve en sağdaki çizginin
kalınlığı olsun; dikeyde en üstte ve en altta bir boşluk var sonrasında
başlıyor, yatayda da bunu ekle.* So:

- **One figure, three jobs.** The cap at each end of a line, a stop a stepped
  value may stand on, and the place the value has got to are the same cross at
  the same size - `metrics.spine.cross`, the arm stepped a rung and halved -
  with equal reach either side. The row card's caps took it too: the `T` with
  a quantity of its own is gone, and `reach` with it.
- **The value's mark is that cross in the accent**, which is the end of the
  wedge here. A wedge points at something, which is right beside a row and
  wrong along the foot of a card; the thickened line that replaced it for a
  pass was a block sitting on a stroke.
- **The line runs on past the travel at both ends**, so a slider at its
  minimum stands an arm inside the cross that ends its line - the run of bare
  line a spine already had above its first row and below its last.
- **And nothing is painted twice.** The dim strokes are two arms with the line
  taking the crossing; the accent one is a single piece, because an opaque
  colour covers the line rather than tinting it. That is what the two earlier
  passes were reaching for by splitting the cross and then by hanging it under
  the line.

**The stepped one then wanted its run solid**, which is the last thing the
screen said: *yatay parçalı olanın solundaki hafif soluk turuncu da düz turuncu
olsun, en sağda ortadaki turuncu bar da aktif olduğu alanın en sağında
görünsün.* Both halves are the same correction. A stop is a place the value has
**stood on**, so the stops behind the mark are places it has been and the run
over them is as solid as the mark itself - the tint is for a continuous value,
which has been at every point behind it and stood at none. And the mark belongs
at the **far edge** of the stop it is on rather than the middle: a stop is a
length the value has reached the end of. It stands on that stop's own stroke,
so the accent covers it instead of landing half a weight beside it.

Checked by rendering `Travel.qml` on its own against a fake ladder - at both
kinds and at 0, mid and full - and then headless through `grabToImage`, which
is the cheaper loop: it costs no shell restart and no screen, so the crossings
were compared at four times life size and the three trail strengths on one
sheet, instead of squinted at.
