# 61. A page that was swapped where it stood · ✅ Done · S

§4.6 again: *transitions are rapid and **directional** - content moves in the
direction of the input*. Ours were rapid and had no direction at all: a
submenu, the next chip along and the next page of the guide all replaced what
was there without anything saying where it had come from.

So a page now **arrives from the side it was reached from** - in from the
right going deeper or forward, in from the left coming back - over the same
110 ms everything else on these surfaces takes.

- **The model is what knows a page changed**, so `turn_seq` / `turn_way` are
  the model's, in `press_seq`'s shape and for `press_seq`'s reason: the page
  is re-sent twice a second, and a turn already drawn must not be drawn
  again. What the panel does with it is a drawing and stays the panel's.
- **The bar had to say the direction rather than have it worked out.** It
  wraps, so the last chip to the first is a step right that looks like a jump
  left to anything comparing indexes. `group_move` leaves the way behind for
  `enter_group`; the guide's `move(step)` does the same.
- **Opening a surface is not a turn.** A surface arriving already has a way of
  arriving, and a page that also slid in from somewhere would be two
  entrances for one press.
- In the menu the offset is added to `cellX` and shared by every tile rather
  than wrapped in a container: it is only ever on its way back to zero, and a
  wrapper would be one more Item between the Flickable and every tile for the
  sake of that. In the guide it is a `Translate`, because that Row is laid out
  by a Column and an assigned `x` would fight the layout.
- It is motion like any other, so `[ui] motion = 0` lands every page where it
  belongs at once - and the countdown on a held row deliberately still does
  not come through there.
