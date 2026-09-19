# 52. The cell with nothing leading to it · ✅ Done · M

Asked for from the sofa: *grid editlerken herhangi bir konuma bir item
koyabilmeliyim, hiç item yokken 3x3'e bir şey koyamam mesela şuan.*

**This reverses a decision item 50 made and wrote down**, so the reversal is
worth the same care the decision got. Phase 1 said:

> **Moving is a reorder, never a coordinate.** First fit always produces a
> valid packing, so a tile can only land somewhere real, and a layout written
> as names survives a different column count, a new tile and another screen.

Every clause of that is still true. What it does not say, and what a hand on
the pad found, is that **an order cannot express an empty cell.** With one tile
on a page there is nothing to be third in - the tile is at the top left and
there is no gesture that moves it anywhere else, because every position in a
one-item order is the same position. Item 51 is exactly the page where that
matters: a page of readings drawn over a game is one whose *whole* content is
where it sits, and the top left corner is where a game puts its own.

So a tile carried in edit mode is now put in a **cell**.

- **A pin takes a tile out of the flow; everything else still flows.** The
  order is still names, and it is still what holds every tile nobody has
  moved - so a page still absorbs a tile added to the config, and a shipped
  page still packs from the top left. Only what somebody deliberately placed
  is placed.
- **That means the new gesture still does the old one's job.** Carrying a tile
  left into the middle of a row pins it there and the rest of the row closes
  up behind it, because first fit runs *after* the pins are claimed. What was
  a special case of reordering is now a consequence of two passes.
- **The cost is real and it is paid in `place`, not given up.** A layout
  written as cells does not survive a column change on its own, which was the
  whole of item 50's argument. A pin is therefore **clamped, never lost**: off
  the edge of a narrower page it is pulled back onto it, and two pins over one
  cell leave the first where it is and hand the second to the flow. The page
  is still a packing rather than a pile - which is the property item 50
  actually wanted, and clamping keeps it without keeping the order.
- **Down goes one row past the bottom, and no further.** That is what makes a
  cell below everything reachable at all - a page grows a row at a time - and
  it is what stops a held direction flinging a tile somewhere a thumb then has
  to walk all the way back from.
- **A carried tile will not walk onto a pinned one.** It would lose the cell
  in `place` and be handed back to the flow, which is a press that goes
  somewhere nobody pointed at. It refuses instead, and the motor answers an
  edge with an edge. An *unpinned* tile is walked through rather than into,
  because that one flows out of the way - the two halves of one rule.
- `omapad check --layout` prints the cells and says which would be clamped at
  the column count the page is drawn at. Clamping is silent by design, and a
  tile quietly pulled back onto the page is the kind of thing this project
  makes a command say out loud.

**What is not in this.** No free pixels and no overlap: a cell is still a cell,
a tile still occupies whole ones, and nothing may sit on top of anything. The
grid was never the thing in the way - only the order was.

**And then the corner turned out not to be the corner** - the second half of
the same report, once a tile could be put in one: *en sağ alta koyduğum item
ekranın en sağ altına gitmiyor, window'un paddingleri vs var; ek olarak gridin
en sonu sabit olmalı, px olarak değil % olarak hesaplasak tüm grid'i.*

Right, and the diagnosis in it is the fix. **A menu page has no last row.** It
is as many rows as its tiles came to and it scrolls past the fold, which is
right for a card - and it means the HUD, drawing that same page, had no cell
that meant *the bottom*. A tile carried to the corner was drawn
`cell_height` pixels per row down from the top and stopped wherever the count
ran out.

So the HUD's grid takes a fixed `[hud] rows` and **a cell there is a share of
the screen rather than a number of pixels**. Those are not two changes: a grid
cannot end where the screen ends and also be measured in pixels from the top.
`n` cells and `n - 1` gaps add back up to the whole, on both axes, which puts
the far edge of the last one exactly on the page's.

- **One number is the density and the limit together**, and there is no
  arrangement of this in which they are two: how many rows the screen is cut
  into *is* how tall a row is. Raise it for thinner tiles, finer placement and
  more presses to cross the page; lower it for fewer, bigger ones.
  `[menu] cell_height` is the same question asked of the menu's own grid, and
  is deliberately allowed a different answer - a card that scrolls does not
  have this problem.
- **`place` gained the downward clamp to match the sideways one.** It has to:
  the menu is where a page is arranged and the menu has no last row, so a tile
  can be carried further down there than this grid has. A menu page passes
  None and is unbounded; a page that is a screen passes its count.
- **The margin is the HUD's own**, not the fullscreen menu's. That one keeps a
  television's overscan clear of a card's first tile; this is a corner
  somebody deliberately put something in, so it defaults to a hair off the edge
  and 0 is the edge. The panel's `ExclusionMode.Normal` does the rest - the
  last row stops where the bars start rather than under one, which is the same
  mechanism that stopped the *first* row coming up under the game bar.
- `omapad check --layout` names both clamps and which column and row a pin
  would be pulled to.

**Found on the way, and it cost twenty minutes:** the panel kept drawing the
old geometry after the file changed. `omarchy-shell shell rescanPlugins` does
not take on a `keepLoaded` panel entry point - which `qml.md` §9 and
`pad-surface.md` both already say, in the paragraph that is easy to read as
being about *adding* a file. It is about editing one too.

**And the bottom edge had two holes in it**, reported the moment there was a
bottom to walk to: *grid'in altına taşıyınca bir itemi bir noktadan sonra
görünmeyen bir yere gidiyor.* Two separate faults with one symptom, which is
why it read as one.

**The menu had no bottom to stop at.** `carry` refused only what was more than
one row past the *packing*, so on a page that is also drawn over a screen a
tile could be carried to row 40. What it did there was worse than nothing:
`place` clamped it back onto the last row, and where something was already
pinned there it lost the cell and fell into the flow - a press that teleports
a tile to the top left.

The coupling this needed was ducked when the clamp was written, and the note
then said so: the menu is where a page is arranged, so the menu is what has to
know the page has an end. `MenuModel` takes `page_rows` now - ids to row
counts, one entry, from `[hud] page` and `[hud] rows` - and it is applied when
the page is **placed** as well as when a tile is carried, so what the menu
draws while somebody is arranging is what the screen will draw. One answer
rather than two that can disagree about where a tile ended up. A page with no
entry keeps growing a row at a time, which is every other page.

**And what was arranged did not reach the screen at all** - reported once the
first two were out of the way: *hud için menüde koyduğum yer arayüze
yansımıyor* - the place I put it in the menu is not where it is on screen when
I leave the menu. Two faults again, one behind the other, and the second was
the real one.

**The two surfaces were not holding one arrangement.** `MenuModel` takes its
own copy of what came off `layout.toml` - deliberately, so rearranging never
writes back into the config - which means `config.layout` is *the file as it
was read* and stops being true the moment anybody carries a tile. `HudModel`
was handed that same `config.layout`, so it was reading the arrangement
somebody had before they started. It takes `self.menu.layout` now, the dict
and not a copy of it, and a test says so: this is exactly the kind of thing
that regresses silently, because both objects look right in isolation.

**And nothing was telling it to pack again.** `hud.repack()` was called from
one place, `set_hud(True)`, so even sharing the dict the cells were the ones
worked out last time the readings were switched on. `hud_rearranged()` is
called from every place the menu mutates the arrangement rather than from
where it is written down - the file is written when edit mode is left, and
what somebody is looking at must not wait for that. It returns at once while
the readings are off, since `set_hud(True)` packs on the way up.

*The same arrangement is not the same packing*, and *the same file is not the
same arrangement*. Neither is obvious from either module on its own, which is
what the two tests are for.

**Found while writing those tests**, and it had been true since the surface
landed: `hud_client` was never swapped for a `FakeViewClient` in the daemon
suite. The comment two lines above the list says what that costs - *a suite
that left them in place would push test payloads at whatever is running on the
machine* - and for the whole of this item's life the suite had been doing
exactly that to the live shell's HUD.

**And the grid did not follow a tile it was carrying.** `reveal` is guarded so
it does not scroll on every arriving line - the heartbeat brings two a second
- but the guard was the selection's **id**, and the one gesture in the whole
surface that moves a tile without changing the selection is carrying one. So
the guard fired, the view stood still, and the tile walked off the bottom of
the visible grid while the button was still being pressed. The key carries the
cell now. A guard on identity where the question is position: the same shape
of mistake as an index for a tile id, one surface along.
