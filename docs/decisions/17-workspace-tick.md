# 17. A tick when the workspace changes · ✅ Done · S

L and R walk workspaces, and from the couch the screen is often the only thing
that says the press landed — which it does not say at all when the workspace
you arrive on is empty. The pad can answer for itself: `hid-nintendo` and
`xpad` both expose `FF_RUMBLE`, so a short nudge is one uploaded effect and one
write.

`rumble = true` on a binding rather than a rule about workspaces: the flag is
where the guide's `desc` already is, and item 09's per-app profiles inherit it
for free. Off everywhere else — a scheme where every press buzzes says nothing.
`InputDevice` now opens the node `O_RDWR` and falls back to read-only, the
effect is uploaded once per connection (an `EVIOCSFF` inside a button press is
latency under the thumb), and a pad with no motors costs one log line.

**Verified by feel, and the defaults came out of it.** The Beitong in NS mode
reports `FF=107030000`, but only its low-frequency motor moves: the
high-frequency one is silent at full magnitude, which is why the first default
- 45 ms of `weak`, the obvious choice for a light tick - felt like nothing at
all. `strong = 0.20` for 60 ms is the lightest of six combinations that still
reads as a click. Duration has a floor of its own: `hid-nintendo` sends rumble
packets every 50 ms, so a shorter pulse can fall between two of them.
