# 32. The browser's own keyboard page · ✅ Done · S

Item 27 built the mechanism and the terminal was the only thing using it, which
made it look like a history feature. It is not: it is the page an app lends the
keyboard, and the browser wants a different one, because what a browser asks you
to type is not a command you have run before — it is **a URL**, the one string
here that has to be exact, and the one a thumbstick is worst at.

So `[profile.browser.osk]` ships as `Web`, and it is built around the address
bar rather than around the browser's menus:

- **`Address bar` (`Ctrl+L`)** puts the caret where you are about to type
  without aiming the pointer at a text field that is four pixels tall from a
  sofa. It is first because it is what the keyboard was opened for.
- **`https://`** types the prefix the omnibox will not guess once what follows
  is not a plain domain, which is the thing that was asked for and the reason
  this item exists.
- **`Go .com` (`Ctrl+Enter`)** wraps what has been typed in `www.`/`.com` and
  opens it. It is the largest saving on the page: a domain becomes the few
  letters in the middle of it, typed one thumb-walk each.
- **`Find` (`Ctrl+F`)** and **`Search tabs` (`Ctrl+Shift+A`)** are the two
  places a browser expects you to type that are not the address bar. Tab search
  matches a title or URL across the window's open and recently closed tabs,
  which from a couch beats walking `L`/`R` past twenty of them.
- **`Reopen tab` (`Ctrl+Shift+T`)** is the one-key undo of a mis-click, and a
  mis-click is what a stick-driven pointer produces.
- **`Zoom −` / `Zoom +`** are the couch's own complaint — a page written for a
  desk, read from a sofa — and they take two entries rather than one because
  zoom is pressed more than once.

**Nothing in the daemon changed.** Every one of those is an `action` entry, the
chord form item 27 added for the terminal's paste, so the page is config: eight
lines in `config/config.toml` and the two tests that assert the shipped page is
what the browser gets. That is the check on 27's shape — a second app wanted a
page of an entirely different kind and needed no code.

**The page is four rows**, so eight short entries is the whole of it, and what
did not fit is written down beside it as a comment: bookmark, history,
downloads, close the tab, full screen, reset the zoom, a private window. The
shortcuts are **Chromium's**, which is what the profile's `match` names —
Firefox reads `Ctrl+Shift+A` as its add-on manager, so a Firefox profile wants
its own page rather than this one stretched over it.
