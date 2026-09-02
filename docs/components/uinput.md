# uinput - `omapad/uinput.py`

The other half of `linux_input.py`: the devices omapad *writes*. A virtual
mouse and a virtual keyboard, created through `/dev/uinput` with the standard
library.

## What is here

- `VirtualDevice` - the setup dance: `UI_SET_EVBIT`/`UI_SET_KEYBIT`/
  `UI_SET_RELBIT` for everything the device will send, `UI_DEV_SETUP` with a
  `uinput_setup` struct, then `UI_DEV_CREATE`. `write()` and `syn()` are the
  only things above it.
- `VirtualMouse` - `move`, `button`, `scroll`, `release_all`. Scrolling emits
  both the classic notch and the hi-res axis; `WHEEL_HI_RES_STEP` (120) is one
  notch as the kernel defines it, not a preference.
- `VirtualKeyboard` - `key`, `chord(mods, code, pressed)`, `release_all`.
- `UinputError` - raised when `/dev/uinput` is missing or not writable, which
  is the one startup failure the daemon cannot work around. `install.sh`
  exists to prevent it; see [`packaging.md`](packaging.md).

## The identities matter

`VENDOR`, `MOUSE_PRODUCT`, `KEYBOARD_PRODUCT` and `IDENTITIES` are not
decoration. A virtual device that looks like a gamepad to another program gets
treated as one - roadmap item 15 is the keyboard that Steam picked up as a
controller. Anything added here declares only the event types it actually
sends, and identifies itself as what it is.

## Rules

- `release_all()` on every path out. A key or button left down by a crashing
  daemon stays down for the session.
- One `syn()` per logical event, not per write.
- Tests replace this whole layer with recorders, so **keep the surface small**:
  the fewer methods the daemon calls, the less a fake has to imitate. See
  [`tests.md`](tests.md).
