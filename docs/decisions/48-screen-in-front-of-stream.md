# 48. The screen in front of the stream · ✅ Done · S

Reported from the sofa: *bazen oyun icin actigimiz ekranlar gamepad destekli
olmuyor ornegin geforce now oyun acarken steam big picturesiz aciliyor ve oyun
launch olmuyor, bu gibi durumlar icin menuden omapad kontrollerini toggle
edebilsek guzel olur.*

The hand-off was right and unusable. 36 established that GeForce NOW opens the
pad the moment its page loads, and 42 established that opening the pad is the
whole question `/proc` can answer - but a cloud client opens it *before there
is a game*. The launcher in front of the stream is a web page: it reads no pad
at all, and by then the pointer that could press its **Play** button has been
handed to it. Every binding stands aside for a window doing nothing with any of
them, and nothing announces itself, because from the pad's side nothing
happened.

**The lock already existed pointing the other way.** 44 built `set_locked` for
the game `/proc` argues about - the pad is the app's, whatever the walk says.
This is the same sentence with the other subject, so it is the same mechanism:
`set_keeping` pins `handed_over` **off** in the place the lock pins it on,
ahead of a profile's `handover = false` and ahead of `/proc`. The two are
exclusive; the second one asked stands.

**And the direction it points settles the rest of it.** The lock has to be
turned off through the one gesture it still allows, which is why 36's chord is
its door and why its notification names the menu. Keeping the pad makes every
gesture work again, so there is nothing to reach past and no chord to spend:
the way out is a plain press. What replaces that care is `when = ["handed_over",
"kept"]` on the row - offered while an app has the pad, *and* for as long as it
is on, so turning it on never takes away the way of turning it off.

It stays on until it is turned off, which is deliberate: the stream that starts
after **Play** does want the pad, and no timer knows when that is. The bar
widget lights up while it is on, and the tooltip names it.
