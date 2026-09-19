# 37. The terminal: Tab, the interrupt and the scrollback · ✅ Done · S

Asked for from the sofa: *make the buttons mean something in a terminal.* The
fourth app to want a profile, and the first whose gap was visible in the config
itself - `[profile.shell]` had shipped since 27 with a keyboard page and **no
bindings at all**, while the browser, the file manager and Discord each had
theirs. A terminal was the app the pad understood least and the one 27 had
already decided was worth a page.

What it needed was not on the pad. A shell is *used* with Tab - the command,
the path and the flag are completed rather than typed - and `Ctrl+C` is the way
out of something that is not coming back. Neither is a key any button sends,
and neither is a thing a pointer can reach. So `Y`, whose right click opens a
menu of two entries in kitty and ghostty and nothing at all in foot and
alacritty, carries both: Tab on the tap, the interrupt on the hold. `Ctrl+L` -
the screen having scrolled past reading - goes on the left stick click, the
middle click's second copy, which is where 35 put Discord's context menu for
the same reason.

**Why the interrupt is not on `B`.** Next to Esc is where it looks like it
belongs, and that was the first draft. But 09's resolution reaches into the
held layers, so a profile's `B` is `ZL` + `B` as well - and that is *close the
window*, which a terminal needs more than any other app on the desktop. `Y`
costs popping the window out instead. The lesson generalised as far as
**38**, which decided the premise was the fault: a profile now stops at the
held layers and pays only at rest. `Ctrl+C` stayed on `Y` anyway — `B` is the
Esc that vim and less want, and an interrupt belongs on a hold.

**And the stick was the actual bug.** 24 gives the right stick to `focus` in
game mode, which sends `[traverse]`'s keys - `next` is Tab and `up` / `down`
are the arrows. At a prompt that is not a poor fit, it is destructive: a thumb
resting on the stick sprays completions across the line and then walks the
shell's history over the top of it. A terminal answers the wheel with its
scrollback, which is what the stick is being pushed for anyway, so
`right_stick = "scroll"` takes it back the way `[profile.browser]` does - the
same exception for the opposite reason, since a browser's focus keys go
somewhere real and just not where the pointer is.

Every key here is the **shell's own** rather than an emulator's, which is what
lets one profile cover all five names in `match`: foot and alacritty have
neither tabs nor a context menu, and the obvious scheme - `Ctrl+Shift+T`,
`Ctrl+Shift+←/→` - would have been dead in two of the five while still
spending `X`. `X` keeps `click:middle`, which in all five pastes the PRIMARY
selection, so select-in-the-browser / click-in-the-terminal already worked and
the clipboard's own `Ctrl+Shift+V` stays on the `Term` page 27 built.

**Nothing in the daemon changed**, the third time in a row: 09's and 27's shape
has now absorbed a browser, a file manager, a chat client and a shell without a
line of Python.

**Revised in use: Tab was the wrong key to spend a button on.** From the sofa a
command is not typed at a prompt, it is aimed at on the on-screen keyboard - and
completing one meant putting the keyboard away, pressing `Y`, and summoning it
again, once per completion. Meanwhile the keyboard's own first page has had a
`Tab` key all along, sitting right where the line being completed is. What that
line actually wants from a button is **Backspace**: the letter aimed at is
regularly not the letter that lands, and there was no way to take one back
without opening the keyboard either. So `Y` is now a plain `key:BACKSPACE`.

**Plain, and that is the second lesson.** A tap/hold binding waits for the
release before its key goes down (`waits_for_release`), which costs the
autorepeat - and Backspace is the one key that is held rather than pressed. A
button that must repeat cannot carry a hold, so the interrupt had to move, and
it went to `X` with `Ctrl+Shift+V` on the tap: `X`'s middle click pastes the
PRIMARY selection, which wants a mouse to have made a selection and a pointer
parked on the prompt - from the couch, the deadest button in a terminal. The
price is the one this item already named, and after **38** it is the whole of
it: what a profile spends, it spends at rest, and the window layer is untouched
either way. A terminal now has no middle click at all, which is what a paste
that works with the clipboard everything else fills is worth.
