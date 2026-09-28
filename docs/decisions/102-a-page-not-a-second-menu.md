# 102. A page, not a second menu · ✅ Done · M

Asked for from the sofa: *quick menuyu ana menunun altina mi tasisak, suan
biraz sacma oldu gibi?* - should the quick menu move under the main menu,
since it has come out a bit absurd; then, on being asked which part: *bence
kontroller de ana menu gibi olsun, quick menu altina eklensin yatay bir
navigasyon degil bir sayfa gibi olsun. kullanici zaten editleyip ekleyip
cikarabilir* - the controls should work like the main menu's, the quick menu
added under it as a page rather than a horizontal row, since tiles can be
edited, added and removed there anyway. And while it was being built: *menu
butonu quick menuyu acsin xbox butonu son acilan sayfayi acsin. game modda da
plus + minus son acilan sayfayi acsin* - the Menu button opens the quick
menu, the Xbox button the page last open, and in game mode MINUS + PLUS the
page last open too.

**What the problem turned out to be.** [85](85-two-menus-two-buttons.md)
split one job across two buttons the way a console does, and then built the
second button a second menu: its own model, its own socket and panel, its own
walk (a wrapping row, up and down turning a value), its own way of guarding a
tile nobody can take back (pressed twice, not held), its own `when` with
places the menu did not have, its own legend and its own layer of bindings.
Every one of those was reasonable alone, and together they were a second
surface that looked like the menu, was reached from the menu and back, and
answered to none of what the menu had learned since - above all
[100](100-one-button-that-adds.md)'s arranging, which never reached it. So
the row could only be changed by editing the config, and the two needed
[98](98-one-backdrop-two-menus.md)'s hand-over, three attempts measured on
the glass, to stop the desktop showing between two screens that meant to be
one place. The console split is about **doors**, and it had been read as two
rooms.

**What was built.**

- **The quick menu is the menu's first page**, `id = "quick"`, a group like
  any other: walked with the D-pad in both directions, rearranged with Y,
  added to with RT. Three bands of nine columns, because a 1080p screen shows
  nine of the twelve: Resume and the two tiles about who the presses go to;
  the volume as a bar and the microphone and deafen as switches; the keyboard
  and Close window.
- **PLUS is `menu:toggle=quick`.** `menu:open` and `menu:toggle` may name a
  chip, and naming one opens the menu there at its first tile, every time -
  PLUS then A is still always back. With the menu up on another page it walks
  the bar there; on that page it closes it.
- **HOME and the chord open the page last open**, the quick page included
  when PLUS was the last to open the menu. The chord is `menu:open`: it is
  HOME for over a game, where HOME's single press may not reach, and it goes
  back to what was being done there rather than to the pause every time.
  [90](90-the-chord-is-the-pause.md) had it open the quick menu because the
  lock was only there; the lock is still one shoulder away on the first
  chip, and a first opening over a game lands on it.
- **The menu's `when` has places.** `window` and `empty` - what is in
  front - beside the states, and a listed place has to hold as well as any
  one state (`menu.offered`). The whole quick page is `when = "window"`: over
  an empty workspace there is nothing to resume, close or type into, the chip
  is not offered, and PLUS opens on the first chip that is - Apps, which is
  what the row's second half used to copy.
- **The lock and its pair are on the quick page only.** They were on Spaces
  too since 90, and one menu holding both copies a shoulder apart is the same
  word twice. Their `stay` went: a pause's verb ends the pause, as it did on
  the row.
- **Close window is held**, with the menu's `confirm`, rather than pressed
  twice. The press-twice existed because the row had a band with room to
  say so, and the menu already has the gesture every other guarded tile
  uses.
- **Removed:** `quick.py`, `QuickMenu.qml`, `Backdrop.qml` and the `swap`
  flag, `quick.sock`, `[bindings.quick]`, `ctl quick`, and the quick layer's
  place in `SURFACES`, the guide and the triggers kept. A config written
  before this still loads: `quick:` parses as the menu spelt the old way
  (`toggle` and `open` name the page), `[quick]` and `[bindings.quick]` are
  dropped, and `omapad check` says so in one line. The shell's `quick` summon
  opens the page.

- **Its card is named after the app in front**, from the next message:
  *menude quick yerine uygulamanin adi yazsin bence* - the app's name rather
  than `Quick`. `names = "window"` on a chip: the desktop entry's name, found
  by window class or id from `apps.py`'s index, or the window's title where
  none answers - a Steam game is `steam_app_N` to the compositor and its
  title is its name. `Quick menu` is the line under it, so the card still
  says which page it is.

**What it cost.**

- **Up and down no longer turn the volume** on the tile in front; the bar is
  taken with A and walked with left and right, or swept with a trigger, like
  every other bar. The row's gesture was quicker for that one tile and a
  second grammar for the whole surface.
- **HOME's first opening lands on the quick page**, since it is the first
  chip and nothing has been remembered yet; [86](86-now-given-out.md) had the
  bar open on Apps. Over an empty workspace it still does.
- **Locking now puts the page away**, because handing the pad over closes the
  menu and always has; the row survived it only by not being the menu.
- **Under the lock the chord may open on another page**, and the lock's tile
  is then a shoulder away rather than in front.

**Rejected.**

- **The row kept, drawn as a band above the menu's bar** - the first answer
  offered, on the argument that a console keeps its quick controls over its
  home rather than inside it. It fixed the look and kept the two grammars,
  and the second message was about the grammars.
- **Keeping `[[quick.items]]` as the page's source**, read into a group. Two
  places a page can be written, and only one of them arrangeable from the
  pad.
