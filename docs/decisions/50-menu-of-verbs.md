# 50. The menu that was a list of verbs · ✅ Done · L

Asked for from the sofa: *the menu and everything in it is still keyboard and
mouse shaped; make it a HUD - music, volume, brightness, all of it grouped
properly, and use the sticks and the vibration while you are at it.*

Which is right, and the shape of what was wrong is worth naming. **Every row in
the menu was a verb.** Press it, something happens, the menu closes. That is a
keyboard shortcut list drawn larger: one column, four D-pad directions and four
face buttons, and a list says every row is worth the same. What is playing is
not worth the same as the row beside it.

Three gaps, and they are separable. There was **no row that held a value** -
volume was two rows saying "up" and "down", brightness two more,
`Controller > Button labels` a submenu of four ticks, eight rows doing the work
of three controls. The daemon was **blind to the machine**: `Action.state` can
ask a setting what it holds and nothing can ask how loud the room is. And the
menu **read a quarter of the pad** - both sticks kept pointing, both triggers
and both shoulders did nothing, and the motor never ticked in it at all.

The whole of it is planned in phases; this entry is what has landed.

**Phase 1 - the head, the bar and the grid. Done.**

The top level is a bar of chips now, walked with L and R, and the tiles of the
group you are on fill the card. Above it a read-only grid carries the day, the
time and whatever command you point at it.

- **`snap.choose` decides which tile is that way**, unchanged. It already
  answered "which rectangle is that way from here?" for the windows a flick
  lands on, and a tile is a rectangle in cells - so the pad walks a page by the
  same rule it walks a desktop rather than by two that can disagree.
  `[menu] bias` is its own number and was measured on golden fixtures rather
  than inherited: windows are large and sparse, tiles small and touching.
- **Left and right stopped being a second way to say Back and Pick.** A single
  column left both free for that; a grid spends both axes on getting about, and
  A and B already said the other two things.
- **Placement is an order, not coordinates.** First fit, in the order the page
  is written, so the order stays authorial and a small tile backfills the hole
  a big one left. A `row_break` tile ends a row; deliberately not a one-cell
  spacer, which holds a hole open at six columns and shifts everything under it
  at four. *(Still how a page the author wrote is laid out, and still how
  every tile nobody has moved is laid out. **52** adds the other half: a tile
  somebody put in a cell is in that cell, and the flow runs around it.)*
- **Identity is a tile id, never an index**, in the model and on the wire. A
  tile changing size re-packs the page under it, so an index is stale the
  moment it is used - and that is due to start happening.
- **Weather, which was refused once and is not a feature now.** 23 turned it
  down because *"putting it here means network I/O in an input daemon, with
  caching, failures and a location to own"*, and that was right.
  A head cell is a command string and a `ttl`: `omarchy-weather-status` owns
  the lookup, `omarchy-weather-location` owns the place, and the helper prints
  its own failure. omapad never learns what weather is.
- **The bar holds places, not verbs**, which cost item 48 its argument - *a row
  you have to go and find is a row that is not there* - for the workspace lock
  and *Keep the controller*. `open_on` answers it the other way round: while
  the condition holds, the menu opens **on** that tile with nothing at all to
  walk to. Nearer than a top-level row in a list of ten ever was.

  *(Answered again, and better, once the HUD was in a hand: the menu **comes
  back where it was left**. Use the lock once and it is what the next press
  opens on, at no cost to any other page - where `open_on` overrode where you
  left off every time. Nothing ships with the key now; it is still there for
  anyone who wants the other behaviour.)*
- The shipped tree gained a **`Now`** group and lost its loose top-level rows.
  What you change while sitting in the room is on the chip the menu opens on;
  `Audio` and `Display` keep what you set when the room changes.

**Found on the way:** a scroll worked out at construction is worked out against
a width of nothing. Both scrollers - the bar and the grid - computed where to
sit while their delegates were still being laid out, and the answer stuck: a
grid that fitted its card ended up scrolled past its own last row with
everything above it off screen, and every tile but the selected one was simply
off the top. Neither is driven from a delegate now, and both re-settle when the
geometry changes rather than only when the state does.

**Phase 2 - the legend, and the two keys a page may spend. Done.**

The foot of the card prints what A, B, X and Y do on the page in front, in the
contract's own order, drawn with the same generated buttons the guide and the
bar print. It is resolved through `guide.button_row(..., brief=True)` - the
guide already turns a binding into words and the bar already reads them short,
so this is that pair one surface along rather than a third opinion, read from
the same place a press reads.

A page may take **X and Y** for a job of its own, with `[menu.items.keys]`.
**Not A or B, and the parser is what says so** rather than a review: the
contract is that A commits and B leaves in every layer and every surface, and
a page that could take either would be the one place on the pad where that
stopped being true. A page taking X keeps `menu:close` on the hold, which is
rule 2 applied one surface along.

**One thing the plan asked for here could not be built, and the evidence is
why.** It wanted `omapad check` to enforce `bindings.md`'s rule that a `short`
is required where the first word of a `desc` is not the meaning. Whether it is
is a judgement no parser can make: of the fourteen shipped bindings with a
multi-word `desc` and no `short`, eleven read perfectly as their first word, so
the warning would be mostly noise. The decidable version - two bindings in one
layer printing the same word on the bar - fires on three places, and all three
are deliberate and already in that file's ledger. A check that only ever names
its own exceptions is a check nobody reads, so `bindings.md` now says out loud
that this rule is a person's and why.

**Nothing in the shipped tree spends one.** That is the answer rather than an
omission: a button is earned only when what it would do is *not reachable on
screen*, and a page of tiles almost always has room for one more tile. Play /
pause on the `Now` page is the worked example of when not to - it is a tile
already, and a tile costs nobody a reflex.

**A gap the legend opened, and closed in the same pass.** `guide.py` builds its
pages from the config and knew nothing about a page's keys, so the moment a
page took X, pressing Y opened a guide that was wrong about X - and the guide
is on Y precisely because you had forgotten what a button does. It takes the
page's table now. What made that cheap is an order that was already right:
`set_guide(True)` rebuilds before it closes the menu, so the page is still
there to be asked.

**Phase 3 - the drawn parts a control tile is made of. Done.**

Fourteen shapes in `assets/shapes/` and a fourth table, `CONTROLS_TO_DRAW`,
writing `shell-plugin/ControlArt.qml`. A dial's rim, its notches, its zone
disc, a needle and a thumb dot; a switch's pill and knob; two chevrons; four
transport marks; and the grip a tile will wear while it is being carried.

**Asked for as "a font, the way we generated one for the buttons" - and it is
not one.** The TrueType half of the generator exists to turn *letters* into
outlines so they can be punched out of a silhouette, and nothing in a dial has
a letter in it. What comes out is the same path data with that step skipped -
the right answer to what was actually wanted, and worth writing down in three
places, because "generate a font for these too" is the obvious reading of what
the buttons do.

**Only the furniture is drawn** - what does not depend on the value. The
needle's rotation, the zone's scale, where the dot sits and how far a knob has
travelled are geometry, and a shape parameterised by a number cannot be drawn
once. It is the split `BadgeArt` already makes between a button and the label
set into it, which is why `BadgeArt` paints both files without knowing there
are two.

A second generated file rather than more entries in the first: `ButtonArt`
cannot be a `pragma Singleton`, so every surface that badges anything
instantiates a copy and only the menu draws these - and `EveryBadgeIsDrawn`
says every label of every layout has art, which a map that also held dials
would turn into a coincidence.

**One rule these have that the buttons do not.** A badge is painted non-zero
normally and even-odd in the stencil style, so a ring drawn as two same-wound
circles is a disc in one of them. That is the trap `stick.svg`'s rim already
taught; the dial's rim is an outer arc wound one way and an inner wound the
other, and `AnnuliSurviveEitherFillRule` is what says so now. `MARK_CAPS` and
the centring test do not apply here at all - a needle is deliberately not
centred.

Nothing is visible on screen at the end of this phase, which is why it sits
before the tiles that use it rather than after.

**Phase 4 - the first two tiles that hold a value. Done.**

A `toggle` and a `choice`, each reading one of the settings the pad can
already change: `control` says which, `reads` says what, and `CONTROL_KINDS`
is the pair they have to make - a switch pointed at a number fails
`omapad check` rather than the sofa. `CHOSEN` is passed into `build()` rather
than imported, so `menu.py` stays the thing that holds state and geometry.

**Eight rows became four tiles.** `On` and `Off` as separate rows was always a
switch written out longhand; a tile that draws which way it is flipped says it
in the space of one. `Hide the pointer` and `Vibration` are switches now, and
`Button style` and `Start in` are walked in place.

**Where the contract's `taken` state was not spent.** A grid spends both axes
on getting about, so a control adjusted sideways has to be taken first - and a
switch has two states. Taking one in order to push it sideways is a mode
nobody needed, so **A acts**: it flips the one and walks the other forward.
What wants taking is a control with a range, and it arrives with one.

**What a choice tile cannot say, and what that decided.** It shows one value,
so the line each row of a tick submenu carried saying *how the choices differ*
has nowhere to go. `Button style` and `Start in` converted because their two
values say the difference themselves. `Button labels` and `Profile` kept their
submenus: getting either wrong scrambles the face buttons, and that line is
exactly what stops you. Seven sentences kept rather than four tiles won, and
`writing.md` carries the ledger.

A choice prints the word it is *called* rather than the word it is stored as -
`playstation` reaches a tile as `PlayStation` - from a `words` map beside the
choices it describes, which also fixed a notification that had been saying
`Button labels: playstation` all along.

**Found on the way:** a tile is one cell tall more often than not, and a name
anchored to the top with a control anchored to the bottom collides there
rather than stacking. One column, and a control tile drops its icon: the
control is the picture.

**Phase 9 - four things the motor can say. Done, and built out of order.**

Built before the slider rather than after it, because the slider's end stop
has nowhere to fire until this exists, and shipping it first means shipping a
silent edge and coming back for it.

The pad here reports `ff=107030000`, which decodes to FF_RUMBLE, FF_PERIODIC,
FF_SQUARE, FF_TRIANGLE, FF_SINE and FF_GAIN - and only `upload_rumble` used
any of it. Now there are four effects uploaded at attach rather than one:
**tick** (a press landed), **edge** (you cannot go further), **commit** (that
took) and **texture** (it is moving, held until something lets go).
`pulse()` is `play("tick")` under its old name, so nothing that called it
changed.

- **How hard and how long are settings; the waveform is not.** A square wave
  is what makes an edge feel like an edge, and turning that into a knob is
  offering to turn a bump into a hum. The cycle count is the same argument one
  field along, so the period is computed from the length rather than named.
- **The texture ships off, and has no fallback.** Off because item 17's rule -
  *a scheme where every press buzzes says nothing* - applies hardest to the
  newest gesture. No fallback because degrading a *continuous* effect onto one
  that must be stopped is the tick that sticks on arriving through a new door,
  and a hum stuck on is not the same risk as a click stuck on. Where the pad
  has no sine wave there is simply no texture.
- **Nothing new was needed in the struct.** `FF_EFFECT_SIZE` was sized from
  `"@HHhhHHHHHIP"` on the first day there was a tick, and that format string
  *is* `ff_periodic_effect` - the union's widest member. The one thing here
  that could have been silently wrong, so a test says it out loud.
- **`EVIOCGEFFECTS` asks how many the pad holds** rather than assuming.
  Uploading past the limit fails on the effect nobody notices is missing, so
  the upload order is the priority order: a pad with three slots keeps the
  three nearest a plain press and says in `journalctl` what it could not take.
- **`omapad check` prints which words this pad can say**, from the same pure
  `plan()` the daemon uploads - one decision, not a report about a different
  pad. On the Series S|X here: all four, with sixteen slots.
- **A held effect is a finger's, the same as a held key.**
  `release_everything()` stops it, so a hum cannot survive a mode switch with
  no press left to blame.
- **None of the new levels reached the pad, deliberately.** `pad-setting.md`
  step 4 puts a setting on the pad when the question arises while holding the
  thing, and *Vibration* already answers the one that does. A switch for the
  texture belongs with the first control that scrubs - until then it would be
  a switch nothing can be felt to obey.

**Phase 5 - the first tile with a range, and the two ways to move it. Done.**

Ten rows across three pages became five bars. `Speed` and `Dead zone` were four
stepping rows each, `Strength` two, and not one of them could say what its
number was or that it had stopped at an end - which is the whole of what a
slider says.

**This is where `taken` finally gets spent.** A grid gives both axes to getting
about, so a tile the selection is only passing over cannot also own left and
right: A takes a slider, and while it is held the two axes are the tile's.
Phase 4 declined to spend it on a switch for the same reason it is right here -
a two-state control had nothing to be held for.

- **A keeps and B puts back**, which is the first place on this pad where B's
  "leave" has had something to undo. Two words rather than one said twice, so
  rule 4 holds on a surface that briefly looked like it would break it.
- **A cancel leaves no trace.** B restores the value *and* takes the setting
  back out of `chosen` where it was not there before: writing a shipped
  default into `settings.toml` freezes it, and the user stops receiving the
  default that changes later. A push nobody kept must not do that.
- **Two ways to one set of numbers.** The D-pad lands on the number you meant,
  growing to `[menu] ramp` the longer a direction is held and starting again
  on a reversal - somebody who has gone too far is not asking for the speed
  they overshot at. Either trigger crosses the whole range in `[menu]
  sweep_ms`, taken or not, because a trigger needs no mode. The sweep moves in
  whole steps of the setting's own `step`, so a value swept to is one the
  D-pad could have landed on.
- **The triggers are read as axes, not bound.** `bindings.md` says of ZL that
  a layer trigger has no binding of its own, and this gives it none: a surface
  layer falls through to nothing, so both are free while the menu is up, and
  how far one is pulled is a question no binding could have asked. The rule is
  now written down there rather than left as a thing this phase did.
- **Nothing is saved or announced until the push stops.** A slider is one
  decision made over a second, not thirty: `settings.toml` written per step is
  thirty chances to be interrupted halfway, `apply_setting` per step
  re-uploads the whole haptic vocabulary for a level nobody stopped on, and a
  notification per step is the screen saying twice what the tile says once.
  The vibration strength ticks the motor exactly once, at the level you kept.
- **Phase 9's vocabulary arrives here.** `commit` on taking and letting go,
  `edge` on the step that first finds the end - once per arrival, because a
  wall you are still pushing against is still one wall - and `texture` held
  while the value is actually moving, which is `[snap] rumble`'s written rule
  about a step repeating under a held button, obeyed rather than restated.

**Found on the way:** a push that had not yet crossed a whole step still has to
count as a push. Settling on "nothing moved this tick" wiped the accumulator
every tick, and a gently pulled trigger - which needs several ticks to earn one
step - could never move the control at all. The hold is counted down off the
same `dt` the sweep integrates over rather than against the clock, so there is
one clock and a loop running slow slows both halves together.

**And a bug the first bad config found.** `build()` recursed into a nested
page without handing down either `settings` or `columns`, so a control below
the top level was never matched against the setting it reads and a span was
never measured against the page. Every control tile in the shipped tree lives
a level down, which is to say the check added in Phase 4 had been running on
nothing at all. Found by deliberately writing a slider onto a switch and
watching `omapad check` say the configuration was fine - which is the exercise
`pad-setting.md` asks for at the end of every setting, and the reason it does.

`Speed` and `Dead zone` also merged into one page, `Sticks`. The argument for
two was that eight stepping rows on one screen is a list nobody reads from
across a room; four bars is not that list.

**Phase 6 - what the machine is doing. Done.**

`omapad/live.py`: how loud it is, how bright, and what is playing. A **source
rather than a surface** - no socket and no control verb, the same shape
`snap.py` and `handover.py` have - and `naming.md` now says that is the
difference rather than an omission.

The daemon was blind to the machine: `Action.state` could ask a setting what it
held and nothing could ask how loud the room was. `Volume` and `Brightness` are
bars showing the real percentage now, and `Music` shows the real track.

- **Nothing in `live.py` runs a command.** It returns the string, and the
  daemon submits it to the worker every other slow thing goes through - a press
  must never wait on `pactl`. A test asserts structurally that the module
  imports neither `subprocess` nor `os`, because that is the rule most easily
  broken without anybody noticing.
- **Every command is a setting.** omapad knows nothing about PulseAudio,
  backlights or MPRIS; it runs a string somebody else wrote and parses what
  comes back, and a machine that answers these questions differently answers
  them by editing `[live]`. An empty string is a reading this machine does not
  have.
- **Volume bypasses `omarchy-audio-output-volume` on purpose.** That helper
  always ends in `omarchy-osd`, so every press would raise Omarchy's own
  overlay *over the tile showing the same number* - the opposite of what
  putting volume on a tile is for. Verified on the machine: moving the bar
  raised no OSD. Brightness keeps its helper, which offers `--no-osd`, because
  DDC, Apple displays and backlights are three code paths omapad must not
  reimplement.
- **The stale-read race, closed before it could be seen.** A read started
  before a write can land after it and rewind the bar for a tenth of a second.
  Every reading carries a generation counter; a write bumps it and an older
  answer is thrown away. The one bug here that would not have looked like a
  bug.
- **A reading that times out keeps its last value.** A parser returning None
  means *no answer*, never *zero*: a tile that empties because a helper was
  slow is worse than one a second stale, and a helper that hangs must never be
  able to empty the HUD.
- **`live:` is `pad:`'s twin.** `live:volume=up` works from any button, with
  the same grammar, because a capability reachable only from the shape it first
  shipped in is a gap rather than a design.

**Where this went a different way from the plan, and why.** The plan had one
media tile with a transport inside it, and A meaning play/pause on a control
that also had to be taken to reach previous and next. Every way of writing that
ended with A meaning two things, or with pausing your music costing two
presses - and pausing is the commonest press on that page.

So the transport is **three tiles**. `Music` plays or pauses on A, the way a
switch flips on A, because it has two states and needs no mode. `Previous` and
`Next` sit either side of it, and left and right walk to them exactly as they
walk to anything else. No button learns a second meaning anywhere, and a tile
costs nobody a reflex - which is the same argument `bindings.md` already makes
about not spending a page key. `canGoNext` and `canGoPrevious` are read and not
drawn: they decide whether a press that way ticks `edge` instead of going
quiet, and a mark on screen you cannot press would say that twice.

**Phase 7 - the dial, and the menu as a surface that streams. Done.**

`Controller > Sticks` had four blind stepping rows: change a number, then go
and find out. There is a dial per stick now, with the dead zone shaded and a
dot where the thumb actually is. Push the stick slowly and the moment the dot
lights is the edge you have set.

**The rule is that the *tile's* kind decides, not the surface's.** The menu
pushes at `[menu] live_hz` only while a gauge carrying `shows` is the tile in
front, and only while the menu is open. Measured here: about 1.5% of a core
with a dial selected and a hand resting on the pad, a quarter of that on any
other tile, and nothing at all with the menu shut.

- **Two pushes, and the second one rebuilds nothing.** `push_menu_live` sends
  `{open, sel, g, live}` with **no `items` key at all**, so `applyState` gets
  past its own guard, finds nothing that is a model, and never reaches
  `fresh()`. One binding re-runs instead of twenty tiles being built. Not a
  new rule - `qml.md` §5.4 already said the panel decides a line says nothing
  new, and this is the daemon declining to send what it knows has not changed.
  `viewsock.md`'s *every push is the whole surface* gains its one exception,
  safe because the heartbeat still carries the whole thing.
- **The cost of that is one rule**, and it is checked rather than reviewed:
  nothing in `Menu.qml` may bind a layout width or height to `root.live`, or a
  layout pass per frame throws away everything it bought. The test was broken
  on purpose to confirm it fails.
- **The claim was measured rather than asserted.** A text test cannot see a
  delegate being built, so a creation counter went into the tile delegate and
  came back out: forty streamed lines rebuilt nothing, and neither did the
  selection moving or edit mode opening. Only a page that is genuinely a
  different list of tiles - another chip, or a tile hidden - rebuilds one.
  Better than the plan predicted, because `fresh()` also catches a full push
  whose items have not changed.
- **The floats are quantised in the daemon**, and not as a noise filter: it is
  what makes the guard work, so a thumb resting off the stick stops the stream
  entirely rather than pushing ADC jitter at a screen nothing is moving on.
- **`sel` rides on the stream on purpose**, so it is meaningful on its own and
  the panel never correlates two of them.
- **Analogue input arrives only here, which is the point.** The grid and the
  controls are all verifiable with a D-pad, so a stick problem can never be
  confused with a navigation or a stepping problem. A stick role of its own,
  `menu`, and the menu becomes the one implicit surface layer that does *not*
  keep the base roles - the left stick walks the tiles, held rather than
  flicked, and the right one keeps the pointer so the promise about the
  pointer staying live under the card is kept by the thumb that was aiming
  with it anyway.

**Two things drawn wrong before they were drawn right.** A dead zone is a
tenth of the travel, so drawn to scale it is four pixels across the middle of
the dial - smaller than the dot it is supposed to contain. A ring was no
better: scaled down it is its own thickness. So the dot's **colour** is what
answers the question - dim while the stick is being swallowed, accent the
moment it is not - which is legible at any value and at any size, and the
shaded disc is left as context rather than as the reading. `dial-zone.svg`
went with that change: a circle of variable radius is `radius: width / 2` and
not a drawing, which is the slider track's argument one shape along.

`dial-needle.svg` went too - drawn in Phase 3 for a rotary the gauge turned out
not to be, since a stick has a position rather than a bearing. `test_assets.py`
gained the invariant that caught it: every generated part is one some kind is
drawn from.

**Phase 8 - the tiles become the person's. Done, and the item closes with it.**

Hold Y on any page and every button on the card means something else. The
legend says which, which is the whole of how the mode is findable - and
`EDIT_KEYS` is six ordinary binding specs that `binding_for` consults before
the page's keys and before the layer's, so **what the legend prints and what a
press does come out of one table**.

The contract holds through the mode. A still commits: picking a tile up and
putting it down is what commit is saying there. B still leaves. X is this
surface's own verb one mode along - `close` becomes `hide`. Y is still the
reach, for the arrangement that is not on screen because it is the one the
config shipped.

- **L and R are the only controls taken from anything**, and only while the
  bar is not what a thumb is aiming at. Nothing is taken from ZL or ZR: a
  height is a control's own shape - a bar is a bar and a dial is round - so
  what a person overrides is how much room *across* a tile gets, which is two
  buttons rather than four.
- **Moving is a reorder, never a coordinate.** First fit always produces a
  valid packing, so a tile can only land somewhere real, and a layout written
  as names survives a different column count, a new tile and another screen.

  *(**Reversed by 52**, and for a reason this bullet does not contain: an
  order cannot express an empty cell, so a page with one tile on it had
  nowhere to put that tile. A carried tile is put in a cell now; everything
  unpinned still flows around it in this order, and `place` clamps a pin
  rather than losing it, which is how the packing property above survives the
  change.)*
- **There is no add page, and that is the better answer.** A hidden tile stays
  drawn where it sits while you are arranging, faded, so removing and
  restoring are the same press on the same tile - no second surface, and
  nothing to go and find. The plan had Y opening a page of removed tiles;
  this is one less screen and one less thing to be lost on.
- **The tree is never mutated.** The arrangement lives in `MenuModel.layout`
  and is applied when a page is shown, so a page reads the same whether it was
  just rearranged or just walked back into - and the config's own order is
  still there for Y to reset to.
- **The merge is three deterministic rules**, because this is where a saved
  arrangement and a changed config meet and that must not be something anybody
  interprets: hidden suppresses only what the config still has, anything new
  is appended, and anything gone is dropped. Editing `config.toml` cannot
  break a layout and a layout cannot hide a tile that did not exist when it
  was written.
- **Syntax corruption and semantic corruption are different failures.** A file
  that will not parse costs the whole arrangement and one warning; an unknown
  id costs that id; a bad span costs that override. Never a `ConfigError` - a
  file the daemon wrote itself must not be how the daemon stops starting.
  Confirmed by hand on the machine: a layout.toml full of rubbish, and the
  daemon came up.
- `omapad check --layout` says what a saved arrangement still resolves to -
  which ids are gone, which are new since it was saved, which are hidden. A
  layout that has quietly lost half its tiles is exactly the kind of thing
  this project makes a command say out loud.
- Every gesture is a `menu:` verb, so the whole mode is drivable with
  `omapad ctl menu edit|pick|hide|restore|wider|narrower|save` and no pad -
  `pad-surface.md` step 6, which is also how it was verified.

**Found on the way.** Pushing a tile down has to take it past the *whole* of
the row below, not up against that row's near edge: taking a tile out of a row
leaves room behind it, so anything short of that packs straight back into the
row it was trying to leave. And `load()` gaining a fourth file re-opened a hole
`shipped_config()` exists to close - a suite that reads the developer's own
`~/.config` tests whichever machine it runs on. Every call site in the suite
now names a layout it does not have.

**What the hold costs.** Y acts on the way back up rather than on the way
down now, the way every tap/hold does - the same beat HOME already has in this
layer.

**Item 50 is done.** The menu that was a list of verbs is a HUD: a head, a bar
of places, a grid of tiles that hold values, a legend, four things the motor
can say, and a page you arrange yourself.

**And then it was looked at from the sofa**, which is the only place any of
this was ever going to be settled. What came back: fill the screen and draw no
panel; blur and darken what is behind; put the row of hints where the game
bar's row already is and take the bar down before the menu draws, or the two
crossfade in one band; come back where it was left; stop saying `Go…` above a
bar of chips that says it already; and **one badge treatment, not two** - every
badge on the pad is a solid silhouette with its label punched out, so the
stick's rim had to go. A ring among them reads as a different colour rather
than as a different button.
