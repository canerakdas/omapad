# 15. The keyboard that looked like a controller to Steam · ✅ Done · S

Opening Steam typed `2` into whatever had focus, again and again — and it was
ours. The virtual keyboard declared the high `KEY_*` range as `0x160-0x2ff`,
and two `BTN_*` blocks sit inside it: `BTN_DPAD_*` (`0x220-0x223`) and the forty
`BTN_TRIGGER_HAPPY` (`0x2c0-0x2e7`). **One button code is enough for `joydev` to
attach a `js*` node**, so every controller scan on the machine — Steam runs one
at startup — found a phantom pad whose buttons were this keyboard's keys, and
sent whatever its desktop layout maps them to.

Fixed by skipping all three BTN blocks; nothing omapad types reaches past
`KEY_MICMUTE` (`0xf8`) anyway. **Verified:** the `js` handler is gone from
`/proc/bus/input/devices`, and a test now refuses any BTN block while requiring
every code in `keymap.KEYS`. Whether Steam still types anything is the user's
to confirm; the remaining suspect is not ours — Steam reads the real pad's
`js0`, which `EVIOCGRAB` on the evdev node does not close.
