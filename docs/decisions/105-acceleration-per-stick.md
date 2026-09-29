# 105. Acceleration, per stick and on the pad · ✅ Done · S

Asked for from the sofa: *Left stick ve right stick için ivmelenme gibi bir
ayar ekler misin daha küçük ve hassas hareketler yapılabilmesi lazım.
İvmelenme tamamen kapatılabilir veya arttırılabilir oran olarak* - a setting
like acceleration for each stick, so smaller and finer moves can be made; one
that can be switched off entirely or raised, as a ratio.

**What the problem turned out to be was reach, not a missing curve.** The
curve was already there: `apply_curve` raises what is left of the push past
the dead zone to a power, and `[pointer] accel` (2.2) and `[scroll] accel`
(2.0) were that power. But it was one number per *role*, reachable only from
a config file, and the question it answers - can this thumb stop on a close
button - is one somebody has while holding the pad and watching the pointer
walk past it. It was the dead zones' story (the Sticks page's comment in
`config.toml` tells it) a second time: a number per job, where the complaint
is about a thumb.

**What was built:**

- **`[pointer] left_accel` and `right_accel`**, read through
  `config.stick_accel(stick)` the way the dead zones are read through
  `stick_deadzone`. `stick_vector()` takes both from the stick, and
  `scroll_vector()` is gone - it was the same function with the other role's
  number in it. Each ships at what its role carried, 2.2 and 2.0, so nothing
  moves for anybody who never touches them.
- **1.0 is off, and says so.** A straight line is the curve switched off:
  half the push is half the speed. Below it the curve bends the other way,
  which is the opposite of what the setting is for, so `omapad check` names a
  value under 1.0 rather than the setting quietly doing its reverse. A swept
  number can now carry `words` for a value that is a place rather than an
  amount, so the bar prints `Off` at its bottom and `2.2×` above it - the
  ratio that was asked for.
- **Two bars on Controller › Sticks**, six cells each, as the page's third
  row. The dials and the four bars come to two whole rows and end together,
  so the third flows the full twelve, and six is the widest span there is.
- **The old keys still load.** `_renamed` hands `[pointer] accel` to the left
  stick and `[scroll] accel` to the right, beside the dead zones it already
  renamed; an explicit per-stick key wins.

**Rejected:**

- **A time ramp on the pointer**, the wheel's `ramp` for aiming. It is the
  other thing called acceleration, and it makes a *held* stick faster, which
  helps crossing a screen and does nothing for stopping on a button - the
  first moment of every push would still be as fast as it is now.
- **Keeping it per role and putting both on the pad.** Four bars for one
  question per thumb, two of which answer for a stick in a role it is not in.
- **Stops instead of a sweep.** Thirty tenths from off to four is a distance
  crossed while watching the pointer, not a handful of places to count.
