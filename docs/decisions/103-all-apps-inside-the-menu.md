# 103. All apps inside the menu · ✅ Done · S

Asked for from the sofa: *menudeki apps altinda all apps omarchy menusunu
aciyor bunu omapad menusunun icinde alt menuyu acacak hale getirebilir miyiz,
arayuze uygun durmuyor suan icin* - `Apps > All apps` opens the Omarchy menu;
could it open a page inside omapad's menu instead, since it does not fit the
interface.

**What the problem turned out to be.** The row was
`exec:omarchy-menu toggle apps`, and its comment said why: *everything
installed, which is a list no controller menu should try to be*. That was
true when the only way to write a page was to write its tiles. Since
[100](100-one-button-that-adds.md) the daemon reads what is installed by the
launcher's own rules, cuts it into kinds and draws each app with its icon -
for the Add picker. So the menu already held the list it said it could not
be, and the one tile that sent a thumb out to a search box was the one tile
on the surface that looked like somebody else's.

**What was built.**

- **`apps` on a tile**: `all` opens a card per kind, a kind opens its apps.
  No `action`, `items`, `from` or `control` beside it, and a kind that does
  not exist is named by `omapad check`.
- **Filled at the press** from the index the daemon already holds, so the
  press waits for nothing; the same press asks for the index again, so an app
  installed since is there the next time.
- **An app is `app_item()`**, the tile Add puts on a page: launch or focus,
  started the way the launcher starts it. The kind cards carry a mark, and
  the picker's kind cards gained the same one.
- **Not a page the picker offers tiles from**: what it holds is whatever the
  last press built.

**What was rejected.** A flat list of every app, alphabetical: sixty tiles is
a page nobody walks to the bottom of. Keeping the launcher behind the row and
restyling it: the launcher's shape is a search field, and restyling does not
give it a thumb.
