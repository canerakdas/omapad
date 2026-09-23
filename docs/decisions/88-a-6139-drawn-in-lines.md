# 88. A 6139, drawn in lines · ✅ Done · S

Asked for from the sofa: *Kronografı minimal teknik line drawing stilinde yap
seiko 6139'un kadranına benzesin ve logo olmasın. 3 tane circle'dan teke
düşürebilirsin* - the chronograph as a minimal technical line drawing, after
the Seiko 6139's dial, with no logo, and the three circles down to one.

**Drawn from a reference, on the fourth attempt.** The first two were drawn
from a description of the watch and were wrong in most of what a description
leaves out. The third was read off photographs of a 6139-6002 and was closer,
and still wrong - short blocks and a flange where the reference has slim
batons and a plain case. What settled it was a line drawing of the dial,
`seiko_6139_dial_01.svg` (*kusursuz değil ama fena değil*), whose proportions
this face now takes number for number:

- **A double hairline case**, two rings close together, and **a track in
  fifths** just inside it: a longer hairline at every minute and four short
  ones between each two - *iki saat arasında biraz daha uzun 4 indis, 4
  indisin arasında da 4 tane daha küçük indis*, which is how the 6139 counts
  a second. At 96 pixels the short ones run together into a band; the
  minutes still stand out of it.
- **Slim batons in outline** at every hour but twelve and six, about a twentieth
  of the radius wide; **the twelve as two bars**; and **at six only a small
  mark at the edge**, because the counter stands where its baton would. Three
  has a baton where the reference and the watch have the day-date window,
  which [84](84-dial-redrawn-from-a-watch.md) asked out.
- **One register at six**, a little under a third of the case's radius
  across, its middle about half the radius down: a hairline ring with a tick
  at every one of thirty minutes, heavier at every fifth. The reference's
  numerals are left out - six pixels high at a tile's size - and its stub of
  a hand is drawn longer, so it still points somewhere from across a room.
- **Hands in outline tapering to a point**, the minute to the batons' outer
  end and the hour a little past their inner one. The chronograph's hand is
  a hairline to the track, a counterweight past the hub, and a hairline on to
  the register's middle. The hub is two hairline rings.

**The panda layout went with it.** [75](75-clock-that-could-measure.md)'s three
sunk discs - running seconds at nine, measured minutes at three, hours at six
- were three solids competing with five hands. The hours measured are in the
figures beside the tile's name, which always said them better; the running
seconds said the face was live, which the sweep says while anything is
measuring. The surface stopped carrying `sc`, how far into the minute the
clock was, which only that register used - and with it the face's timer
sleeps while the stopwatch is stopped instead of waking four times a second.

**The grid.** `ShapesSitOnTheGrid` wants a straight run parallel to an axis
on whole units, which a hairline centred on the axis cannot be - both its
edges whole makes it an even number of units wide. The rule exists because
`Metrics.badge` snaps a badge's unit to whole pixels; nothing snaps a clock,
which is drawn at whatever square the tile leaves it, so a whole unit there
was never a whole pixel. The dial's ticks and its register are exempt, and
the test says why.

The time-of-day clock shares the face, batons and hands, so it is this
drawing too - the file's whole argument, one drawing on every surface that
draws a clock. The HUD's copy is due to be rewritten anyway.

**Left out:** the day-date window (see above), the register's numerals, and
the name on the dial, as asked.
