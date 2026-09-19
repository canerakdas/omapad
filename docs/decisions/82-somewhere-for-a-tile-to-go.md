# 82. Somewhere for a tile to go · ✅ Done · M

Asked for from the sofa, after a year of arranging pages: *menude gizleme var
ama kaldirma veya farkli bir navigasyon altina tasimak yok, kaldirilan oge bir
pencereye eklensin, kendisi degil ismi gorunse bile yeter, baska bir yere
gecip birakabilelim veya duzenleme modunda lt rt sayfa degistirmeye yarasin.*

Two halves of one gap. A tile could be taken off a page and put back on the
same page, and that was all: there was no way to move one to another page,
and no way to see what you had taken off a page you were not standing on.
The **cause** of both is that a removed tile was drawn faded in the cell it
came out of - which is somewhere it can only come back to.

**The strip along the foot is where a tile that is on no page stands.** Its
name, the page it came from, and everything taken off every other page beside
it. The ask sets its own bar - *ismi gorunse bile yeter* - and that is the
right bar: a second grid of the same cells would be a second page to arrange
on a surface whose whole argument is that there is one page in front of you.

**Removing and hiding turned out to be one thing.** A tile in the strip when
you leave edit mode is a tile off that page, which is exactly what hiding one
always was; what is new is that it can be picked up again somewhere else. So
`hidden` became `removed` in the file - one name in the interface, the file
and the docs, `writing.md` rule 14 - and the old name is still read, because
a file written before this must not lose what somebody put away.

**The shoulders walk the bar while the hand is empty**, which is the other
half of the ask and the answer to *lt rt sayfa degistirmeye yarasin*. Not the
triggers: L and R already walk the bar everywhere else in this layer, and the
mode borrowing them for a size was only ever defensible while the bar was not
what a thumb was aiming at. With a tile in the hand it still is not - a page
is not walked away from while carrying something - so there the shoulders are
narrower and wider and the triggers shorter and taller, exactly as 70 left
them.

**Which made the table three tables.** `EDIT_KEYS`, `EDIT_CARRY_KEYS`,
`EDIT_REMOVED_KEYS`, chosen by what the hand is holding, with the legend
built from whichever is in force. Eight rows where half of them answer a
press with nothing is not a legend, it is a list; six rows that are all true
is. `EDIT_ANY` is the union and it is what `surface_override` asks, because a
trigger that says nothing must still not let the window layer open under the
card.

**One fact in one place.** A moved tile is recorded by the page **holding**
it - `adopted = ["apps/steam"]`, a reference because an id is unique only on
the page that wrote it - and the page it came from says nothing at all. What
a page has lost is derived from every `adopted` list there is. Two tables
that each had a say could disagree; one cannot, so resetting the page holding
a tile hands it straight home and no hand-edited file can strand one.

**Down at the bottom of the page reaches the strip**, and costs no button:
that press did nothing at all before. A seventh button for a direction
already pointing at the thing would have been the legend growing to say so.

**And it is what makes a page inside a page reachable.** A picks a tile up
rather than drilling in while editing, so there was no gesture that could
carry a tile two levels down. The strip outliving the mode is the answer
without a gesture: take it off, B, walk in, Y, place it.

**Two shapes were tried and dropped.** A chip on the **bar** holding the
removed tiles as real tiles reads better and needs a tile to be carried
*between* pages - which is the drawing of a tile that belongs to no page, the
exact thing the faded cell was avoiding. And a **single-slot** hand, one tile
at a time, has to answer what a second tile does: displace the first
silently, or refuse. A list that is simply the `removed` ids read across
every page answers neither question, and is the same data the file already
held.

**And it found a cache that could not tell three specs apart.** A binding
built for a page key is held under `(page, button)`, which was one answer per
button until one button became three: L kept the binding built with an empty
hand, so the bar walked while the legend said `Narrower`. `edit_state()`
names the table and the name is the rest of the key - the same shape of fault
70 found in `surface_override`, one layer down, and caught the same way: the
test presses the button rather than calling the command.

**`omapad check --layout` gained the other half of the report** - which page
is holding what, what this page has lost, and a reference that names nothing
- and lost a phantom: it slugged an explicit `id`, and counted a `row_break`
as a tile called `row`.
