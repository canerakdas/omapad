# 62. A bar that came off its own edge · ✅ Done · S

Asked for from the sofa: *alttaki bar çok altta kalmış ve sağında solunda çok
boşluk var, onu eski haline çevirelim.*

`[ui] safe_area` was a twentieth of each side and it was applied whenever game
mode was on, on the argument that game mode is when a television is being
used. The screen it was being read on was a 1920×1200 monitor, which crops
nothing: 96 pixels off each end of the bar and 60 off the bottom, for a set
that was not there. A bar standing a centimetre clear of three edges says
something about the shape of the screen, which is not what a safe area is for.

Two things were wrong and they are separate:

- **The default.** Game mode is the *couch environment*, not proof of a
  television - the README has said so since item 24 - and a couch is as often
  a desk monitor turned up loud. So it ships at **0**. A guess that costs a
  twentieth of every edge is worse than no guess: the person on a set knows
  they are on one and can write the line, and the person on a monitor has no
  way of knowing what took their margins away.
- **What the share moved.** The bar's ground was being inset bodily. The rule
  it is borrowed from says the opposite - backgrounds bleed to the edge, and
  what has to be *read* comes in - so the ground fills the window again at any
  safe share and the row of hints inside it is what moves. That is what makes
  the setting worth turning on rather than something that looks broken when
  you do.

It also caught two tests reading the developer's own `~/.config/omapad`:
`config_module.load(path)` merges settings.toml over whatever a test wrote, so
three validation tests had been passing on this machine's answers rather than
on the file they wrote - and started failing the day somebody turned the sound
on from the menu. `only()` in `test_daemon.py` is the fix, and
`test_packaging.py` now fails any test that loads a config without naming the
layers under it.
