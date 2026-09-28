# 101. A marimba and a vibraphone · ✅ Done · S

Asked from the sofa, over one evening: *ses altyapisini [bir referans] ornek
alarak yapalim bence, bunu localde senin kullanabilecegin araclar ile
generate edebilir miyiz* - make the sounds after a reference, generated here
with what is on the machine; *varsayilan seti degistir* - make them the set
that ships; *suan cok ince sesler ve tiz* - thin and shrill; *simdi de kutuk
gibi oldu* - now like a log; *su damlasi gibi bir ses var ... piyano notasi
etc gibi* - there is a water drop in it, try notes, a piano and the like;
*marimba en sevdigim oldu*; *once hard olarak guncelle* - the marimba,
hard mallet; then *menu ve back sesi kotu oldu* - the menu's sound and the
back's were bad - and, of four of each, *show 4, back 4*; then *navigasyon
icin dogru sesleri bulduk ancak menu, back, error, commit gibi sesler icin
... farkli sesleri denememiz lazim* - the walk is right, the events want a
different sound - with the error named as *100 olunca cikan ses*, the one
a value makes at its maximum, which is `edge`; and, of five, the
vibraphone. The reference is left unnamed here on purpose, as it is in the
code.

**What the problem turned out to be.** Not the vocabulary and not the levels:
[94](94-sounds-measured-where-heard.md) had held both against the standards
there are, and both stand. It was the one miss 94 recorded and left to a
pack - **timbre**. Two or three sines per voice is thin, and Brewster's
earcon rules ask for a richer timbre that a family shares.

Getting there took five sets, each auditioned from a reel rather than
argued for, and each failure named a variable:

| Set | Heard as | What it said |
|---|---|---|
| Unpitched knocks, 2.1 kHz, 5 ms ring | thin and shrill | the pitch and the ring are the weight |
| The same an octave down, three times the ring, low-passed | a log | brightness is not optional; a knock with none is dead |
| A third of the way back | better, but a water drop | the drop was the glide - a struck note whose pitch slides |
| Piano, electric piano, marimba, kalimba, the knock without a glide | the marimba | a pitched bar, with direction carried by intervals |
| Marimba with a soft, hard, room and low mallet; vibraphone; xylophone | hard and soft | the mallet is the variable left, and hard was chosen to ship first |
| Hard everywhere, show a rolled D-F#-A, back A falling to D | the show and the back bad | figures read as a notification and a falling one as an error; the two that arrive and leave want one soft stroke each |
| Show, commit, back and edge as bell, synth pluck, tine, vibraphone and pure tone, inside the marimba walk | the vibraphone | the events are a second family: the same bar in metal, ringing longer |

## Built

- **Two families.** The walk and the tick are the marimba, below; the
  show, the commit, the back and the edge are the vibraphone - aluminium
  bars tuned 1, 4, 10, ringing for most of a second and cut by the cue's
  own length, with the mallet given as which overtones it wakes: the soft
  one barely the fourth, the hard one the tenth as well. `bar = "soft"` or
  `"hard"` on a voice is what puts it there. Brewster's rule read at the
  level of families: two kinds of thing, two timbres.
- **One modelled marimba bar in `assets/sounds.py`.** Three modes at a
  marimba's carved ratios - 1, 3.93, 9.2 - each decaying at its own rate,
  shorter on higher notes; the resonator tube under it, which holds the
  fundamental a hair sharp and comes up over 4 ms, the bloom that separates
  a marimba from a xylophone; and the mallet, given as the length of a
  half-sine push against the bar. That one number, `MALLET_MS`, is how hard
  the mallet is: a pulse that long has little energy above its inverse, so
  3.5 ms is a yarn head and 0.9 ms - what ships - rings the upper modes.
- **Notes, not glides.** The D major pentatonic without its B - D, E, F
  sharp, A - so any two cues overlapping are consonant. The move E, the
  page turns F sharp and D, the tick the A below; the show a low D and its
  octave swelling in over 25 ms, the commit D and A struck together hard,
  the back the tick's A soft and muffled, the edge two quick strokes of the
  lowest D and its octave - the octave the stronger, for the television -
  soft and muffled.
- **Longer, inside what a press allows.** The commit is 160 ms, the show
  180, and `test_sound.py`'s ceilings rose with them; the move stays at
  45 ms because a held direction ramps to a step every 28 ms on the
  keyboard. Every voice keeps its `lufs`, the order they rise in and the
  peak ceiling; the meter and `--measure` are untouched.

## Rejected

- **Samples.** A sample is a licence to carry and a file nobody can edit,
  which is why the set was synthesised in the first place.
- **Naming the reference.** This history is published, and a set that is
  its own does not need to borrow a name to explain itself.
- **The sines as a second built-in pack.** `[sound] pack` already takes any
  directory, and a second shipped set is a second set to keep at its levels.

## Not built

- **Soft for the frequent touches too.** The move and the page turns on the
  soft marimba mallet, the way a player carries weight, was auditioned;
  the walk was heard as right as it is, and a per-voice marimba mallet
  went with the need for it.
- **A separate sound for a list's end and a value's maximum.** `edge` is
  both, and it was heard as the error. A refusal and the end of a list
  are close enough to share it; splitting them is a new voice in five
  places.
- **Takes.** Every `move` is the same file, and a quick walk is a machine
  gun of it; four takes a few cents and a little mallet apart, played in
  turn, is the standard answer. It needs the bank to know about takes.
- **48 kHz, dither and a true-peak test.** The sink here only runs at
  48 kHz, so every cue is resampled on every play; the quietest files peak
  near 0.02, so their tails are a few bits deep and want TPDF dither; and
  the ceiling is held on samples, not between them.

**Still owed**, as 94 left it: none of this has been heard across the room on
the television the levels are measured for.
