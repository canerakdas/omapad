# 96. A weight asked for is not a weight drawn · ✅ Done · M

Asked for at the desk: *projeyi incele ve tipografi icin neler yapabiliriz
listele. temaya gore font weight etc* - look over the project and list what
typography could do, a weight that follows the theme among it. The list came
back with eight items, and the answer was to do all of them.

**What the problem turned out to be was not the theme.** Twenty-four places on
the surfaces asked for `Font.Medium`, and the face Omarchy ships -
JetBrainsMono Nerd Font - is a Regular and a Bold and nothing between. Qt
answers 500 from the face at or below it, so every one of those was drawn
Regular: the nav card you are on, the choice that is ticked in a card of
rows, the chip the mapping screen is asking about. Each of them said *this
one* in colour alone, and a theme whose accent sits near its text said it in
nothing. Nothing warned, because `fontInfo.weight` hands back the number that
was asked for. `fontInfo.styleName` is the only thing Qt reports that names
the face it drew, and a render of 300 to 800 side by side is what showed 400
and 500 were one face.

**What was built:**

- **`metrics.weight`**, four jobs named like the type ladder: `body`, `name`,
  `strong`, `display`. Seventeen probe `Text`s in the surface's family - one
  per half step - report the face each weight is drawn in, and `strong`
  climbs until the face changes from `body`'s. On the shipped font that is
  Bold; on a family with a Medium it is Medium; on a family of one face it
  asks for Bold and Qt emboldens it. The other three take whatever face Qt
  finds, because a label is already set apart by its size and its place, and
  climbing would put every label on a page in the weight meant for one row.
- **The theme's word**, without Omarchy knowing: `[font]
  omapad-weight-<job>` in a theme's `shell.toml` lands in
  `Style.fontOverrides`, because Omarchy parses every key of that table as a
  number and keeps the ones it has no name for.
- **The ground's**: half a step on `name` and `strong` when the theme's text
  is darker than its ground, measured with `Ink.luminance` rather than read
  from the theme's name.
- **The person's**: `[ui] weight`, four worded stops from `Lighter` to
  `Heaviest`, on the pad as `Controller > Text weight` beside `Corners`;
  `game_weight` for the sofa, following `weight` until it is written down.
- **The badges keep their own**: `buttonArt.weight`, generated beside
  `buttonArt.family`, because the one face `ButtonArt` loads is Medium.
- **Tracking and figures** named once: `metrics.tracking.caps` (an eighth,
  where the quick menu had nine hundredths for the same caption) and
  `masthead`, and `metrics.figures` for `tnum`.
- **The rest of the surfaces crossed to the silver ladder** - guide, mapping
  screen, keyboard, bar, HUD - at the nearest rung, and the shell's list of
  sizes left `Metrics` with them, so the "never mix the two" rule is kept by
  there being one.
- **The family falls back on `OMARCHY_MENU_FONT`** (`Style.font.menuFamily`)
  rather than the desktop's face: these surfaces are menus, and somebody who
  has chosen a face for Omarchy's has said what a menu is set in.

`WeightTests` in `tests/test_shell_plugin.py` fails on a `Font.*` weight, a
`font.bold`, a hand-written tracking or a size off the old list at a call
site, and on a word in the surface's family with no weight at all - unset is
Normal, which neither the theme nor the slider can reach.

**Rejected:** shipping a Medium face. It would fix the shipped font and no
other, and `[ui] font` exists so somebody can set the surfaces in anything.

**Rejected:** a whole step up for every word on a light theme. Noto answers
450 from its Medium, so on a family with faces between a light theme would
have set a page of labels in the weight meant for the row in force. Half a
step on the two jobs that must stand out lands on the same face either side
on a family of whole faces, and is the difference and no more on a variable
one.

**Rejected:** weight scaled from the reading distance. `game_scale` ships at
1.0 because the menu is already drawn for a sofa (see the comment on it), so
the scale says nothing about how far away somebody is. `game_weight` is the
same question asked of a person instead.

**What it costs:** the in-force row is now Bold on the shipped face, which is
a heavier difference than the Medium that was drawn in the design - it is
the one the font has. Seventeen hidden `Text`s per surface, measured once per
family. And the guide's and the mapping screen's headings are a rung larger
(`lead`, 20 at the default theme, from 16), because `heading` had nowhere
nearer to land.
