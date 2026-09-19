# 41. The pointer that kept sliding across the game · ✅ Done · S

Reported from the sofa, on the other machine: *I opened a game and it seemed to
be taking mouse input the whole time; I could not use the pad's buttons because
of it.*

**Handing the pad over was only ever half done.** `handed_over` was asked in
exactly one place - `allowed()` - and that place decides what a *press* may do.
Nothing asked it about the sticks. `drain_events` went on storing the axes,
`needs_tick` went on asking only whether a layer had given a stick a role, and
`tick` -> `emit_cursor` went on moving the virtual mouse. So the buttons stood
aside politely while the left stick drove the desktop's pointer across the game
underneath.

**The comment for `handover_siblings` had already written the symptom down** -
"a Proton game leaves the pad driving the desktop's pointer over the top of it"
- and filed it as what happens when the *detection* fails. It was also what
happened when the detection worked. It went unseen from the couch because game
mode turns both sticks off by default, and the report came from a desk.

**A stick gets no `reaches_past`.** What buys a button its way past an app
holding the pad is being a gesture the game does not ask for - a chord, an
announced hold - and a stick pushed over is the one input every game does ask
for. There is nothing to opt back in to, so `stick_roles()` returns
`("none", "none")` and that is the whole of it. `surface_open()` is now the one
question the grab, `allowed()` and the sticks all ask, so a surface takes the
pad, the presses and the pointer back together: the keyboard is pointed at with
a stick.

**What it made worse is the item that was already open.** An application that
opens the pad without being a game - Discord polls the Gamepad API for its own
keybinds - now lost the pointer as well as its bindings for as long as it was
focused. That is 42, and it went in on the same afternoon.
