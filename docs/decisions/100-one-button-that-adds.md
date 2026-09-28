# 100. One button that adds · ✅ Done · M

Asked for from the sofa, in three messages:
*apps'e istenilen bir uygulamanin arayuzden eklenebilmesini saglayabilir
miyiz* - can any app be added to `Apps` from the interface; then *her tusa
bir sey atamayalim, bir tus belirleyelim o tusun altinda ekleyebileceklerini
listeleyelim alt menu alt menu olarak gitsin* - not a button for each thing,
one button with what can be added listed under it, submenu by submenu; then
*suan bir sey kaldirinca removed altina gidiyor, bunu da kaldiralim bence
zaten eklenebilecek geri. menudeki tum elementleri eklenebilir yapamasak bile
yapabildigimiz kadarini yapalim* - drop the removed strip, since a removed
tile can simply be added back, and make as much of the menu addable as can
be; and *omarchy menusu nasil yapiyor bunu hazir varsa onu kullan* - use what
Omarchy's own menu already has for this.

**What the problem turned out to be.** Three questions that were one. A page
could be given a heading from the pad (95) and a tile from another page (82),
each through a gesture of its own - RT for one, the strip along the foot for
the other - and an installed app through neither: only the config could name
one. A third gesture for apps was the first answer offered and the one taken
back, because it is the shape the second message refused. What goes on a page
is one question, and the answer to one question is one list.

**What was built.**

- **RT is Add** while arranging, and opens a picker: pages pushed on the
  menu's own stack, walked the way every page is - A goes in or adds, B comes
  back out one list, and off the first one back onto the page. Three rows:
  `Heading`, `Apps` (a page per kind of app) and `Menu` (a page per page of
  the tree, each of its tiles). What is added arrives in the hand, just before
  the tile the selection was on. See `menu.md`, *Removing, and the one button
  that adds*.
- **The strip is gone.** X takes a tile off its page exactly as before - into
  that page's `removed` - and `Add > Menu > <page>` lists it as `Not on any
  page`. The same list moves a tile from where it stands to the page in
  front, which is what the strip was for. `rm`, `rmat`, `EDIT_REMOVED_KEYS`,
  `place`, `put_back` and `ctl menu removed N` went with it.
- **Apps are Omarchy's.** The shell's app list is QML and is handed only to a
  plugin that is a menu; the menu's state is the daemon's. So `apps.py` reads
  the entries itself and applies every rule the launcher applies - its hiding
  script run as it is, its hides file, its desktop ids - and starts an app
  with the command the launcher does, focusing one already open where the
  entry names its window class. The panel finds the icon the way
  `AppLibrary.iconSource` does, and an app is the one tile drawn with a
  picture rather than a glyph. See `apps.md`.
- An app on a page is part of the arrangement, as a heading made from the pad
  is: `[layout.<page>.apps]`, a name under `@` to a desktop id. One not
  installed is not drawn and not forgotten.

**Rejected.**

- **A button per kind** - RT a heading, LT an app, a third for a tile. The
  second message. Also the arithmetic: the empty-handed state has one button
  left, and a legend is worth having only while it is short.
- **Typing to filter the apps**, with the keyboard that already types a
  heading over the menu. Forty-four apps cut into eight kinds is at most a
  page or two a kind, and a keyboard on a pad is the slowest way to say a
  word; kinds are what a console's own library is cut into.
- **Keeping the strip beside the picker.** Two doors to one list, and one of
  them spent a band of the card on every page while the mode was on.
- **Becoming a `menu` plugin to be handed the launcher's list.** It would be
  the shell's list on the shell's side, and the menu - the only thing that
  needs it - is not there.
- **Every row inside a card of rows, and listed rows** (`from`). A row is
  drawn by the card around it and a listed one is a command's answer that
  changes while the daemon runs; neither is a tile that could stand on a
  page. Everything `pages_of` knows, which is every tile of every page, is
  offered.
