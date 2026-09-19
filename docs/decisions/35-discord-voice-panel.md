# 35. Discord: the face buttons as a voice panel · ✅ Done · S

Asked for from the sofa: *let the face buttons run Discord's shortcuts — mute
the mic, mute the mic and the sound, and two more.* The third app to want a
profile, and the first to want the **face** buttons: 09 gave the browser the
shoulders and the file manager a single key, and both left `A` and `B` alone
because a console scheme is what everything else expects of them.

Discord is where leaving them alone is the wrong answer. Its most-pressed
controls are not on screen where a pointer can reach them — mute and deafen sit
in a strip the size of a thumbnail, in the corner furthest from wherever you
are aiming, and you have to hit one of them *mid-sentence*. Meanwhile `A` is
Enter in an app whose messages are sent by the keyboard's own `ZR`, so what the
console scheme was protecting there was worth very little.

So `[profile.discord]` puts the voice panel on the four face buttons: `A` mutes
the microphone (`Ctrl+Shift+M`), `B` deafens (`Ctrl+Shift+D`) — the pair, next
to each other on the pad the way they are in the app — `X` is the quick
switcher (`Ctrl+K`), and `Y` answers an incoming call (`Ctrl+Enter`), which is
the one thing here that is *timed*. Enter and Esc survive as holds, which is
also how Esc keeps declining a call.

**The right click was the interesting cost.** Taking `Y` takes the context
menu, and in Discord that menu is how a message is replied to and reacted to —
more than the binding was worth. It moves to the left stick click, whose middle
click was `X`'s twice over, so nothing that mattered paid for it. That is the
same displacement `[profile.browser]` makes, and it reached into the window
layer the same way: `ZL` + left stick no longer pinned the window while Discord
was focused. **38 ended that** — the pin is back, in Discord as everywhere.

The keyboard gets a `Chat` page over 27's mechanism, and it is a third kind of
page again: a terminal's is what you have already run, a browser's is the
address bar, and a chat app's is **the sentences you send without meaning
anything by them** — `brb`, `omw`, `gg`, three keys instead of nine aimed
letters. The other half is the pickers, all of which open something that is
then typed into: search, emoji, GIF, mark the server read, pins.

**Nothing in the daemon changed here either**, which is the second check on
27's and 09's shape: the pad's most app-specific scheme so far is config.

**What the order of the profiles turned out to be worth.** Omarchy installs
Discord as a webapp as readily as pacman installs the client, and a webapp is a
Chromium window: class `chrome-discord.com__channels_@me-Default`, which
matches `chrome` as squarely as it matches `discord`. 09 resolves the first
profile declared, so written where the other app profiles are this would have
lost to `[profile.browser]` on exactly the install that needs it most - the
buttons would have been the browser's tab switcher over a chat client. It is
declared first, with the reason written beside it. That is the first time the
declaration order has decided anything, and it is the shape of the next
question rather than a fault: a webapp is two applications wearing one class.

**And the menu grew the couch's short list.** `Apps` had Steam, a browser, a
terminal and *everything installed*; it now leads with the four a sofa actually
reaches for - Steam Big Picture, Discord, Spotify, YouTube: the game, the people
you are playing with, the music and the television. Three of them launch **or
focus**, because with a pointer this slow a second copy of a chat client is
never what was asked for. Discord's row is the one worth reading: an `exec:`
action is a shell command, so the row asks `omarchy-cmd-present` which of the
two Discords is installed at the moment it is pressed rather than the config
guessing at install time.
