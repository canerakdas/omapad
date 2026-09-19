# 27. A keyboard page the app in front lends it · ✅ Done · M

Typing a command letter by letter with a thumbstick is the worst thing the
keyboard asks of anybody — and in a terminal it is also the most predictable
thing it is asked for, because the command you want is nearly always one you
have already run. So a profile can now hand the keyboard **a page of its own**:
it joins the cycle `L`/`R` already walk (`abc` → `&123` → `Fn` → `Term`) for as
long as its window is in front, and leaves the cycle with it.

```toml
[profile.shell.osk]
label = "Term"
keys = ["git status", "sudo pacman -Syu"]
from = "tac ~/.bash_history | awk '!/^#/ && length > 2 && length < 60 && !seen[$0]++' | head -8"
```

**`from` is what keeps the daemon out of the shell business.** Its output is
one entry per line, so which history file, and whether bash or atuin or zsh is
answering, is a line of config rather than a branch in Python — the same reason
`hypr:` bindings are Lua expressions rather than a dispatcher table.

Four things had to move to make the page possible, and each is small:

- **The page-turn cell stopped naming a layer.** It said `layer:sym`, which
  cannot be right when how many pages exist depends on what is focused. It now
  says `layer:next` and the *model* prints where that goes, because the running
  order is the only thing that knows.
- **A key can type a string** (`text:`), and a character is not a keycode: the
  same XKB table the printed labels are read out of is inverted into
  character → chord, so an entry types the same thing the keys say. A character
  the layout cannot make is dropped rather than typed wrong.
- **The page is laid out the way text is read**, not the way a grid is walked:
  a short entry shares its row, a long one takes it alone, and it stops at four
  rows so the keyboard keeps the height it has on every other page. The width
  budget comes from the bottom row it shares, so the columns still line up when
  the page turns.
- **The command runs when the keyboard opens**, not when focus moves, and its
  output is kept for `ttl` seconds. A window change is not worth spawning a
  shell for, and the page cannot be read while the keyboard is down.

**Caveat, and it is bash's:** the history file is only written when the shell
exits, so what the terminal in front has typed today is not in it. One line —
`PROMPT_COMMAND='history -a'` — fixes it, and the README says so where the
page is documented.

**An entry can also carry a chord** (`action`, the same grammar `[osk.keys]`
uses) rather than a string, and that closes the `Paste` key's oldest wrong
answer: the bottom row sends `Ctrl+V`, which is right everywhere except a
terminal, and a terminal's `Ctrl+Shift+V` now sits on the terminal's own page.
That is the shape the problem always wanted — not a key that means two things
depending on where it is, but the app's page carrying the key that is only
right there. The chord is parsed at config load, so `omapad check` names the
profile instead of the daemon failing when the page is drawn.
