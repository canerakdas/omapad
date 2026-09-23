# 87. What the couch could not reach · ✅ Done · M

Asked for from the sofa, after a review of every page and card: *Menü
kategorileri ve altındaki kartları incele, eklenmesi veya çıkarılması gereken
özellikleri çıkar* - then *önerilerini yapalım*. The review found four things
a person holding the pad had to get up for, and three tiles standing on the
wrong page.

**What had to be got up for.** Each is a helper Omarchy already ships, so
nothing here is new machinery - it is the pad reaching what the keyboard
already could:

| Tile | Page | Through | Because |
|---|---|---|---|
| `Night light` | `Display` | `live:nightlight`, `omarchy-toggle-nightlight` | The evening's other answer to the light, beside `Brightness` |
| `Stay awake` | `Display` | `live:stay_awake`, `omarchy-toggle-idle` | Idle is measured by nothing being touched, and a film is watched without touching anything |
| `Screens` | `Display` | Omarchy's laptop and mirror switches | A laptop plugged into a television had no way to put the picture on the television alone |
| `Paired devices`, `Bluetooth`, `Pair a device` | `System` | `omarchy-bluetooth-device`, `live:bluetooth`, Omarchy's panel | A pad that slept, or headphones that went to a phone, came back only from a keyboard |

The three switches are `live:` readings rather than `exec:` rows, the way
[VRR](../components/live.md) is: a switch is a tile that shows which way it
is set, and a row cannot. They go through Omarchy's helpers and never round
them, because its bar and its own menu read what those write.

**`Screens` is listed**, not written: the three answers only exist while there
is a laptop panel and a second screen, and anywhere else the card says `No
second screen` and offers nothing to press. Unlike the resolution and the
rate beside it, what it sets survives a reload - Omarchy's switches write the
toggles its config reads.

**`Paired devices` connects and does not disconnect.** A device is let go by
switching it off, and the device most often on that list is the pad holding
the menu. More than one row can be connected at once, which a listing's tick
was not built for: a press moves the tick onto the row pressed until the page
is read again.

**Pairing is Omarchy's panel, not a second one.** Finding something new is a
search that takes longer than `[menu] list_timeout_ms` lets a listing run, and
a list that fills while you watch it. The panel hangs off Omarchy's bar, which
game mode takes away, so the row asks whether it opened and says so in a
notification where it did not - a press that does nothing is the one outcome
a sofa cannot diagnose.

**Moved: `Motion`, `Corners`, `Tile fill` to `Controller`.** They are what
omapad draws, not what the screen is set to, and on `Display` beside
`Resolution` they read as three questions about the television. They are the
last band of `Controller` now, next to `Button style`, which was already the
page of omapad's own look. Their argument - you set them by watching the
tiles change under the thumb - holds on any page, since every page is tiles.

**And three more, a round later** - *2'yi yapalım*:

| Tile | Where | Through | Because |
|---|---|---|---|
| `Do not disturb` | `Spaces`, beside the lock | `live:dnd`, Omarchy's notification service | A toast over a film, or over a game on a call. A question about the session in front, like the lock |
| `Record` | the quick menu, after `Screenshot` | `omarchy-capture-screenrecording --fullscreen --with-desktop-audio` | The region picker is aimed with a mouse; the same press stops it |
| `Network` | `System`, a row of its own | `omarchy-network-status`, and Omarchy's network panel on a press | Whether the machine is online is the first question when a stream will not start |

`Record` is a switch and is still an `exec:`. A `live:` write runs in the
daemon's worker and only its shell is killed at `timeout_ms`, so a recorder it
started would live inside omapad's own service and die with the next restart.
`exec:` has a scope of its own.

`Network` stands on a row of its own under the stopwatch, with half of that row
empty. Asked whether the stopwatch should give its cell up - to `Readings`, or
out of the shipped menu - the answer was that it stays.

`Display`'s nav line reads the focused monitor, as the cards on it always did;
it read the first one, which on a laptop with a television is the laptop.

**Rejected:**

- **A list of Wi-Fi networks.** Choosing one needs a password, and a
  password is a keyboard. `Network` reads the connection and hands the
  choosing to Omarchy's panel.
- **The pad's battery.** The review suggested it, and the mockup's Controller
  hero leads with it, but the pad on this machine is behind an XInput dongle
  that reports no `power_supply` - a tile for a number nothing answers.
- **`Start in` as a one-cell choice.** Suggested for the room it takes, and
  the wrong way round: it was a `choice` and became a card because its two
  values need the sentence each carries (`pad-menu`'s own worked example).
- **Moving `Dictate to clipboard` off `Sound`.** Suggested as a keyboard
  setting on a sound page; on a second look it stands under `Microphone`,
  and where the microphone's words land is that card's question.
- **A disconnect row, and a forget row.** See above; forgetting is rare,
  destructive and one press from the panel.
