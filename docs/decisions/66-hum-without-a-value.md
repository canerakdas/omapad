# 66. A hum that said nothing about the value under it · ✅ Done · S

Asked for in the same sitting as the line above it, and it is the same ask one
sense along: *yatay çizgiyi hareket ettirirken A'ya basmadan önceki hâline göre
ne kadar soldan sağa giderse sağda titreşim artsın, yukarı aşağıda da sabit,
solda titreşim artsın veya azalsın - tabi bunları yaparken mevcut titreşimin
strengthine göre yapsın.*

The `texture` said *it is moving*, which is the least interesting thing about a
value being changed: the thumb already knows it is moving, because it is the
thing doing it. What it says now is **which way, and how far from where it
stood** - the same sentence the line on screen says, told to the hand.

- **Two motors, which is why it stopped being a sine.** A pad wires its
  low-frequency motor on the left and its high-frequency one on the right, so a
  value pushed right is felt on the right - and a periodic effect carries one
  magnitude, which cannot say a direction. `texture` is plain `FF_RUMBLE` now.
  It loses a waveform a pad might not have, so it also stops being the one word
  some pads simply cannot say.
- **The mark is where A found the value.** `_menu_from` is set by `menu_take()`
  - the same point B puts the value back to - and the level is the distance
  from it. Push back to the mark and the motor goes quiet; a pause in the
  middle of pushing is not letting go of the mark, because A has not been let
  go of. A control moved with no mode at all - a trigger sweeps one without
  taking it - marks where the push began and lets that go when it settles.
- **Up and down were already still**, which is the third clause of the ask and
  cost nothing: a taken control answers one axis because a range is one
  dimension, so there was nothing to keep the motor from following.
- **The strength is the one already chosen.** The floor is `texture_strength`,
  so the first step away is felt at all; the ceiling is the **tick's** own
  `strong` - the `Strength` tile on the Controller page - so a value pushed the
  whole way is exactly as strong as a press, and turning the vibration down
  turns this down with it. No new setting: both ends were numbers somebody had
  already set.
- **`aim()` re-uploads the effect in place.** `EVIOCSFF` with an effect's own
  id replaces what the slot holds, and a running effect picks the new level up
  without a gap. One round trip per step is the thing `rumble.py` otherwise
  refuses - allowed because it *is* the press's own work rather than something
  happening underneath one - and it is skipped where the magnitudes have not
  changed, which is most steps of a held repeat.
- **And it ships on**, where it shipped off. Roadmap 17's rule is that a scheme
  where every press buzzes says nothing; a buzz that says *which way you just
  pushed* is not that scheme.

**The scale came back out a day later**, from the same chair: *titreşimleri de
artan azalan değil sabit bir hâle getirelim, hamlenin yapıldığı yönde titreşim
verebilirsek daha iyi olur geri bildirim için; dikeyde dpad olduğu için sola
titreşim versek daha iyi.* Right on all three counts. A level that rose with
the distance from where a push began is a second reading of the number the
tile is already printing, and what a hand on a control is asking is whether
the push landed - so it is one flat level, `texture_strength`, re-derived at
0.25 because a level that used to climb to a ceiling could afford to start
low. The side is the whole message: `aim(name, side)` takes "left", "right" or
"both". And **up and down are the left motor**, both of them, because a list
is walked with the D-pad and the D-pad is under that thumb - which is also the
first time the vertical instrument is felt at all, on the same
`MENU_SCRUB_HOLD` a scrubbed slider uses. `_menu_from` and `menu_share()` went
with the scale.

**And the vertical went back out**, from the same chair again: *yatay ve dikey
seçilebilir sliderlar için fazla titreşim ekledik gibi.* It was: a list walked
up and down has one motor for both ways, so what it says is that something
moved without saying which - which is the scheme `texture` was kept switched
off for, arriving by the back door. It was doubled feedback too, the only
place on the surface that was both heard and felt, and long: 200 ms against a
press's 60. So a row step is heard and not felt like every other step of a
selection, `menu_feel` answers a range and nothing else, and the sentence in
`rumble.md` about a plain move has the row in it now.
