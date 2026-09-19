# 21. The pad that answered to its neighbour's name · ✅ Done (screen; profile still assumed) · M

`X` produced a right click. Not a binding problem: omapad names buttons by
what is *printed on the pad* and picks a profile from what the *driver
reports*, and those are two independent facts. The Beitong KP20 in NS mode
sends Switch Pro codes out of a shell printed with Xbox letters, so `0x134` -
`BTN_WEST`, the left face button, which the `nintendo_pro` profile calls `Y`
because on a Switch that is where Y is - arrives under the finger the case
labels `X`. Every face button answers to a neighbour. No profile can know
this: nothing in the protocol says what is silkscreened on the plastic.

Measured rather than argued about. The pad advertises exactly the 14 codes the
profile expects, so the code set was never wrong - only which physical button
each one sits under.

**What landed** is a fourth surface rather than another profile, because the
same gap opens for every pad nobody has written a profile for: `mapping.py`,
`mapping.sock`, `Mapping.qml`, a `Map controller` menu row and
`omapad ctl map <toggle|open|close|skip|back|restart|save|cancel>`. It asks
for each printed name in turn and writes down the code that answers, into
`~/.config/omapad/mapping.toml` - keyed by device identity, because the KP20
has one per hardware mode and different codes in each. Resolution runs
profile → measured → hand-written `[device.buttons]`, so a measurement beats an
assumption and a person still beats both. Saving re-resolves the live device,
so it takes effect without a restart.

Three things fall out of the screen reading the pad **raw** - it must, since
the map that would turn a code into a name is the thing being fixed - and each
needed its own answer, none of which can be inferred from a pad whose map is in
doubt: a code that already has a name **skips** the step being asked (an Xbox
pad has no Capture, and it doubles as the answer to pressing one twice);
holding anything for 2.5s leaves without saving; and the last step asks for
**A** to save and **B** to discard *in the names just learned*, which makes the
act of saving the cheapest possible test of what was learned. An axis pulled
past 0.6 of its travel is recorded as a trigger rather than a button, so the
XInput pads that report ZL/ZR as axes map the two the console scheme clicks
with.

**Found on the way:** the test suite called `config_module.load()`, which
merges `~/.config/omapad` over the defaults - so it tested whichever machine
it ran on, and started failing the moment this session wrote a binding into the
developer's own config. Pinned to the shipped defaults.

**Still open.** The shipped `nintendo_pro` profile still names the KP20's face
buttons by Nintendo printing, so a fresh install of this pad is still wrong
until someone runs the screen. Splitting a profile into *protocol* (codes,
whether the triggers are analog) and *printing* (which letter sits at which
position), with `[device] labels = "xbox" | "nintendo"`, is the fix that would
make the screen unnecessary for pads we already know. The screen also cannot
map the D-pad - it is a hat, not a button, on every pad seen so far - and it
takes the sticks on faith.
