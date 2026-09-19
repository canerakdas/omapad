# 19. The stick that rested half a range off centre · ✅ Done · S

The cursor walked into the bottom-left corner the moment the pad connected, and
a full push the other way only held it still. Measured rather than guessed:
every axis on the Beitong KP20 in NS mode rests at half the advertised range
and then uses only that half — X and RX span `-32767..0`, Y and RY span
`0..32767`, each resting at its own midpoint. Against the advertised centre of
0 that reads as a permanent half deflection, and the far end of the stick is
exactly the centre the daemon thought it had.

Two things had to change together. The neutral comes from the value the axis
actually rests at, read with one `EVIOCGABS` at connect — an earlier attempt
sampled `EV_ABS` events over a window instead and never fired once, because
this pad sends nothing at all while it sits still. And the half-range becomes
the distance to the *nearer* advertised end, so both directions still reach
full speed on a half-range axis; a pad that rests where it claims to is
unaffected, its two ends being equidistant. A rest beyond `recenter_limit`
is taken for a stick held during connect and left alone, since calibrating
onto it would freeze that direction for the session.

The limit shipped at 0.90, and that was too generous by far: an Xbox Elite
Series 2 connected with a thumb on the right stick rested 0.84 out, calibrated,
and scrolled Discord and YouTube downwards at full speed for the rest of the
session — the leftover half-range was a sixth of the advertised one, so the
stick's real centre read as a full deflection. 0.60 is the default now, one
notch clear of the 0.50 a pad genuinely resting off centre sits at, and a
refused calibration says so in the log.

**Verified:** `axis 0x00 rests -0.50 off centre` for all four axes on connect,
and the measured travel — rest `-16379`, ends `-32542` and `0` — reproduced
across two runs.
