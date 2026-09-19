# 29. Showing the screen and asking: the assistant · 📦 Shelved · L

**Built, then taken back out (2026-08-31)** to ship a smaller feature set
first: it was the one thing here that spawned a model, a recorder and a
transcriber, and the four programs behind it are four ways for the pad to
stop working for reasons that have nothing to do with the pad. Everything
below is what it was, and stands as the design for putting it back.
`assist.py`, `ai.py`, `history.py`, `Assist.qml` and `tests/test_assist.py`
are kept verbatim in `../../tries/omapad-assist-removed-2026-08-31/`,
along with the config and the callers as they were before the removal.

From the couch, the shortest way to explain where you are stuck is to show the
screen. One button photographs it, listens to what you are asking, and prints
the answer on a panel sized to be read. Working in game mode was the point; it
works exactly the same on the desktop.

**Three new modules, without bending any of the existing limits.** `assist.py`
is the surface itself (pure, it runs no commands), `ai.py` the providers and the
thread that does the work, `history.py` the per-game transcript. The panel is
`shell-plugin/Assist.qml`, the sixth surface.

**No third-party package, and no HTTP.** Every assistant worth pointing at
already ships a CLI that takes prose on stdin and prints prose on stdout, and
each carries its own login. A provider became a **command template**: `claude`
ships, and `codex` / `gemini` / `grok` stand there as starting points. An HTTP
client would have reached exactly one provider, and would have wanted the API
key the CLIs already have.

**The audio never goes to the model.** No provider accepts audio, so speech is
transcribed on this machine (voxtype / whisper.cpp). Two side benefits: you can
read what you asked before it is sent — the only way you notice the microphone
misheard you — and the history stays `grep`-able.

**Memory is per game, not per session.** A question asked over a game is almost
never the first question, so the transcript is filed under the window class
(`~/.local/state/omapad/assist/<class>.jsonl`) and a new conversation opens
with the tail of it. A provider that can resume its own session is better than
repeating lines — it has kept the screenshots as well — so `mode = "auto"` tries
resuming first, `lines` stands there as the portable answer, and `off` writes
nothing.

**Every phase says its own name.** There is a dead moment of a few seconds in
the middle of a question sent to a model, and over a fullscreen game that is
indistinguishable from a button that did not work. So the panel walks through
photographing / listening / understanding / thinking; the listening phase is the
only movement and the only counter, because just then the user is the side that
has to do something.

**The shutter before the panel.** Our own surfaces are on the overlay layer, so
if they were open `grim` would photograph them too. The panel opens *after* the
photo, and in the ~90 ms in between the thing that says the press arrived is the
rumble.

Verified end to end: photo → answer ~9 s, a follow-up question ~3 s, the
transcript and the session id written to disk, the panel drawn on screen.

**Two traps, both hit and both fixed:**

- The `resume` template did not carry the first turn's permissions
  (`--allowedTools Read --add-dir`), so reading the new screenshot was refused
  on a follow-up question. Because the provider returned that as an *answer*, no
  error appeared anywhere — only the answer itself said "I could not read it".
- On the QML side the socket data was assigned with bare names; when one of them
  landed on something read-only and threw, the `catch` swallowed it and **every
  field after it** silently stopped being applied. `open` was last, so the
  symptom was "a panel that has its data and never comes up". All of them are
  now written explicitly with `root.`, and the `catch` logs instead of staying
  quiet.

**Left open when it was shelved:** asking a question by typing on the panel
(through the OSK) was never wired up — every question was either spoken or the
ready-made one in `[assist] prompt`. And `assist:talk` could not be used as the
hold half of a tap/hold pair: the hold half fires press and release together,
leaving no interval to speak in. Putting it behind a confirmed hold would need
a mechanism of its own.
