# 51. The machine, under whatever is playing · ✅ Done · M

Item 50 ends with a HUD whose every tile is something you change - how loud,
how bright, which mode, what is playing. **None of them is something you only
watch.** Game mode takes Omarchy's bar away, which is right for a screen read
from a sofa and leaves the question that bar was answering: what the machine
is actually doing while it does it.

Two things, and the second one is why this is not just a menu page.

**A source for the readings, which is `live.py` one layer down.** `live.py` is
what the *desktop* is doing and every one of its answers is a helper's;
`sysinfo.py` is what the *kernel* publishes about the hardware, so almost all
of them are a file read - and a file read is not something to spawn a shell
for twice a second. That split is the whole of why it is a second module
rather than six more entries in the first: `command()` is what tells the loop
which of the two kinds a reading is, file reads happen on the loop and `cmd:`
goes through the worker like everything slow.

- **Where each reading comes from is a setting**, in one grammar,
  `<how>:<where>`, because there is no answer here true of every machine:
  which chip holds a temperature, whether the graphics card publishes a load,
  whether anything on this desktop knows a game's frame rate. `file:` and
  `cmd:` are the two that reach anything, which is why the list of *hows* does
  not have to grow every time a driver publishes something new.
- **An empty source is a reading this machine does not have.** Nothing asks
  for it and no tile is drawn. Three ship with a source; a temperature
  deliberately does not, because every machine has hwmon chips and their
  numbers are not interchangeable - one picked for somebody prints the wrong
  number under the right word, and a wrong number is worse than no tile.
- **hwmon is found by the name a chip publishes, never by its number**:
  `hwmon4` is a battery on one boot and a network card on the next.
- **A busy share is measured across an interval**, so the first read answers
  nothing at all. `/proc/stat` counts ticks since boot, and one read of it is
  what the machine has averaged since it was switched on - a number that is
  true, useless, and indistinguishable from a real one once it is on a tile.
- **A reading that stops answering keeps its last value**; one that has never
  answered has none, and that is how a tile knows not to draw itself. A sensor
  briefly busy must not be able to empty the screen.
- **Only a share has a bar.** A thermometer's top of scale is a number
  somebody would have to invent, and a bar against an invented maximum says a
  different thing on every machine it is read on - so there is no `v` in the
  payload and no track drawn, rather than a bar that lies.

**And a surface that is deliberately not a surface of its own design.** What
the HUD draws is an ordinary `[[menu.items]]` group: `hud.py` packs it with
`menu.arrange` and `menu.place`, the same two functions the menu packs a page
with, and the panel draws those cells over the whole screen instead of inside
a card. So the tiles are written where every other tile is written, arranged
with the gesture that arranges every other page, and the arrangement lands in
the same `layout.toml` under the same page id. There is no second place to
configure this and no second packer to disagree with the first.

- **It is a setting, not a surface that is opened.** `[hud] show` is in
  `CHOSEN`, so the switch on the page, `omapad ctl hud on` and the settings
  file are three doors onto one value - and it is still on tomorrow. Every
  other surface is opened and closed; this one is decided once and left, which
  is why `set_hud()` closes nothing, takes no grab and has no layer.
- **It reads no pad input at all**, which is the whole of what lets it sit
  over a game: no `[bindings.hud]`, no `SURFACE_LAYERS` entry, no keyboard
  focus and an empty input region. The moment it could take a press it would
  be in the way of the thing it is drawn over.
- **`WlrLayer.Top`, not Overlay.** The menu, the guide and the keyboard are
  Overlay, so opening one of them covers the readings rather than fighting
  them for the same band of screen. `ExclusionMode.Normal` then asks for what
  is left once the bars have taken their strips, which is why no bar geometry
  travels in this payload and the top row can never come up under the game
  bar.
- **Two rules about what it refuses to draw**, and both are the point: a tile
  that is not a readout is not drawn - the page holds its own switch, and a
  switch is a thing to press - and a reading that has never answered draws
  nothing at all, which is what makes one page correct on two machines. The
  **whole** page is still packed, including what will not be drawn, or a
  readout would not land in the cell the menu shows it in.
- **The menu does not follow the second rule**, deliberately. A readout there
  keeps its label with the value blank, because the menu is where you go to
  find out that a reading has no source on this machine - and a row that
  vanished could not tell you that.

**Found on the way, and it is the finding of this item.** The daemon half
landed first and was complete: the model, the sources, the settings, the
validation, the control verb, the wiring, the heartbeat. It streamed to
`hud.sock` twice a second. **Nothing drew a pixel, and nothing said so** -
every test passed, `omapad check` was happy, and the only symptom was a blank
screen, which is also exactly what the surface looks like switched off.
`pad-surface.md` makes the panel step 7 of nine for this reason, and a
checklist is a thing you can get to step 6 of. So the rule is a test now:
`EverySocketIsDrawn` walks every `ViewClient` in the daemon, finds the
`SurfaceSocket` that listens on it and the entry point that mounts that panel,
and fails in both directions - a socket nobody draws, and a panel waiting on a
name the daemon never binds.

`omapad check` gained the other half of the same argument: it prints what each
reading says right now, because **a source pointed at nothing and a reading
nobody asked for look identical on screen**. Both draw no tile. The only way
to tell them apart was to read the source, and this project's habit is to make
a command say it out loud.
