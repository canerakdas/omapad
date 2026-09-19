# 42. The application that opens a pad it is not played with · ✅ Done · S

Left open since the handover landed, and 41 made it cost the pointer rather
than a few bindings: **Discord holds the pad without being a game.** It polls
the Gamepad API so its own keybinds can answer a controller, so `/proc` sees
it holding the pad for as long as it is focused, and the profile 35 built -
the voice panel on the face buttons, the thing you aim at with the pointer the
rest of the time - stood aside in the one window it exists for.

**No amount of looking at /proc answers this**, and that is why it sat open.
The question `wants_pad` asks is *has the focused app opened the pad*; the one
worth asking is *does holding this app's pad mean driving this app*, and the
second is a fact about the application rather than about its file descriptors.
The note called for an ignore list by window class, and then a whole second
matcher would have existed beside `[profile.<name>]`, which already matches
applications by window class and is where every other thing an application
disagrees about is written down.

**So it is a profile key.** `handover = false`, one line, shipped on
`[profile.discord]` and nowhere else. `update_handover()` asks the active
profile before it asks `/proc`. The ordering fell out of it:
`seed_active_window` asked about the pad *before* swapping the profile in, so
every focus change had been answering for the window that had just left -
invisible while the answer came from a pid, wrong the moment it came from a
class.

**The dangerous direction is the other one**, and the comment in the config
says so: a game that lands here is a game the pad cannot reach. The key only
ever refuses the hand-off - there is no `handover = true` that forces one,
because being handed a pad you have not opened is not a thing to ask for.
