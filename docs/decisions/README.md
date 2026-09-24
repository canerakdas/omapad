# Decisions

One file per decision, in the order they were made. A file says what the
problem turned out to be, what was built, what was rejected and what it cost -
the reasoning behind a line of code that the code itself cannot carry.

**The number is the stable part.** Decisions cite each other by it ("44 built
`set_locked`"), and so do the component documents and a comment or two in the
daemon (`omapad/config.py` on 17's rule, `docs/components/osk.md` on 29). A
file gets renamed when a better name turns up; it never gets renumbered, and a
number is never reused.

Nothing here is a plan. What is still open - and the three items below that are
not finished - is [`../roadmap.md`](../roadmap.md).

| Status | Meaning |
|---|---|
| **✅ Done** | Implemented in the working tree and covered by tests or a live check. |
| **🗑 Removed** | Was built, then taken back out. The entry stays for what it measured. |
| **📦 Shelved** | Was built and worked, then taken back out to keep the shipped set small. The code is kept; the entry is the design for putting it back. |
| **Buildable** | No unknowns in the way. The cost is the work itself, not the risk. |
| **Constrained** | Possible, but partial or unreliable in ways worth deciding on before starting. |

Effort is relative: **S** hours, **M** a day or so, **L** more than that. Items
marked **Verified** inside were tested against the running compositor and the
installed shell rather than estimated from documentation.

**01-14 were planned**, in four phases: the two faults that were simply wrong
(01, 02), the keyboard (03-06, 13), how the pad behaves everywhere else (07-10)
and what a person can change by hand (11, 14). The button scheme (07) settled
first because it decided what the keyboard's own map (03) should be, and 09 -
per-application profiles - landed once the map underneath had a shape to layer
over. **Everything from 15 on came out of using the thing**, from the sofa,
and is in the order it was found.

| # | Decision | Status | Effort | What it settled |
|---|---|---|---|---|
| 01 | [Cycle through empty workspaces too](01-empty-workspaces.md) | ✅ Done | S | `r+1` walks every workspace in the monitor's range, not only the used ones. |
| 02 | [The screensaver interrupting the keyboard](02-screensaver-and-keyboard.md) | ✅ Done | S | An idle inhibitor under the keyboard - pad navigation is no Wayland input at all. |
| 03 | [Controller buttons inside the keyboard](03-controller-buttons-in-keyboard.md) | ✅ Done | S | The keyboard's own buttons live in `[bindings.osk]`; both triggers mean a row. |
| 04 | [Page one: a whole keyboard](04-whole-keyboard-page.md) | ✅ Done | M | Page one is a whole keyboard, with the key widths a keyboard actually uses. |
| 05 | [Shifted characters, shown dimmer](05-shifted-characters.md) | ✅ Done | S | A key prints its shift alternative, dimmer, beside what it types. |
| 06 | [Three pages instead of two](06-three-keyboard-pages.md) | ✅ Done | S | Three pages ship - `main`, `sym`, `fn`; the machinery already took any number. |
| 07 | [A console-shaped default scheme](07-console-shaped-scheme.md) | ✅ Done | M | The default map is console-shaped: A confirms, B goes back, the triggers click. |
| 08 | [A menu instead of a keyboard shortcut](08-menu-instead-of-shortcut.md) | ✅ Done | M | `PLUS` opens a list, not a radial; holding it still reaches Omarchy's own menu. |
| 09 | [Per-application button profiles](09-per-application-profiles.md) | ✅ Done | M | `[profile.<name>]`, matched on window class and layered over the defaults. |
| 10 | [A hint bar along the bottom](10-hint-bar.md) | Buildable | M | The desktop half of the hint bar; the game-mode half arrived as 23's readout. |
| 11 | [A place to see the bindings](11-bindings-guide.md) | ✅ Done | M | The guide: a surface that draws the bindings as the buttons they are on. |
| 12 | [Disabling the keyboard in password fields](12-password-fields.md) | Constrained | L | Field-level detection is unreachable on this stack - the seat is fcitx5's. |
| 13 | [Caps Lock that works, and shows](13-caps-lock.md) | ✅ Done | S | `Caps` sends both shifts, because Omarchy's layout takes the key for Compose. |
| 14 | [Per-key labels and actions](14-per-key-labels.md) | ✅ Done | S | `[osk.keys]` overrides what a key shows or does, keyed by the action it has. |
| 15 | [The keyboard that looked like a controller to Steam](15-keyboard-seen-as-controller.md) | ✅ Done | S | The virtual keyboard declared `BTN_*` codes, so every scan found a phantom pad. |
| 16 | [Apps launched from the pad died with the daemon](16-launched-apps-died.md) | ✅ Done | S | A launched app gets its own scope, so restarting the daemon stops killing it. |
| 17 | [A tick when the workspace changes](17-workspace-tick.md) | ✅ Done | S | A rumble tick on the workspace walk, because an empty workspace says nothing. |
| 18 | [Shoulders that are global except where they aren't](18-shoulders-per-profile.md) | ✅ Done (browser pilot) | M | The shoulders go to the profile where the app has a tab switcher of its own. |
| 19 | [The stick that rested half a range off centre](19-stick-resting-off-centre.md) | ✅ Done | S | The KP20 rests half a range off centre on every axis - measured, then corrected. |
| 20 | [Left click in a browser the pad had been handed to](20-left-click-after-handover.md) | ✅ Done | S | Game mode stopped swallowing everything that was not a `mode:` action. |
| 21 | [The pad that answered to its neighbour's name](21-pad-answered-neighbours-name.md) | ✅ Done (screen; profile still assumed) | M | Names come from the pad's print, the profile from the driver: the mapping screen. |
| 22 | [A bar that knows about the pad](22-bar-widget.md) | ✅ Done (unverified on screen) | S | A widget in Omarchy's bar, rather than a second bar fighting it for the edge. |
| 23 | [A bar for game mode, and item 10 arriving through the side door](23-game-bar.md) | ✅ Done | M | The game bar is a readout, not a bar: nothing in game mode has a pointer to click. |
| 24 | [Game mode was the wrong shape](24-game-mode-shape.md) | ✅ Done | L | Handing over is asked of the program through `/proc`, not guessed from a mode. |
| 25 | [The band of nothing under the menu](25-band-under-the-menu.md) | ✅ Done | S | The menu card's uneven band, measured off screenshots and evened up. |
| 26 | [A badge that was promising something a press would not do](26-badge-promising-too-much.md) | ✅ Done | S | A badge dims where the press behind it does not do what the badge promises. |
| 27 | [A keyboard page the app in front lends it](27-app-lent-keyboard-page.md) | ✅ Done | M | A profile lends the keyboard a page of its own, in the cycle `L`/`R` walk. |
| 28 | [Not having to aim: the ring cursor, snap and traversal](28-ring-cursor-and-snap.md) | ✅ Done | M | The ring cursor, `snap:` and traversal - the answer to aiming with a thumbstick. |
| 29 | [Showing the screen and asking: the assistant](29-assistant.md) | 📦 Shelved | L | Built and taken back out; the text is the design for putting it back. |
| 30 | [The keyboard opening by itself](30-keyboard-opening-itself.md) | 🗑 Removed | S | Field level is closed on Wayland and window level was worse than nothing. |
| 31 | [Buttons drawn as drawings, not as rounded rectangles](31-buttons-as-drawings.md) | ✅ Done | M | Badges are generated from `assets/shapes/`, not drawn three times in QML. |
| 32 | [The browser's own keyboard page](32-browser-keyboard-page.md) | ✅ Done | S | The browser lends the keyboard a URL page - the one string that has to be exact. |
| 33 | [The game behind Big Picture, and the menu rows that died with it](33-game-behind-big-picture.md) | ✅ Done | S | Steam stays in front of its game: the `Windows` rows, and a row that fired too early. |
| 34 | [Asking for a button the pad does not print, and a menu for the pad](34-mapping-screen-badges.md) | ✅ Done | M | The mapping screen prints the pad's own letters, and the settings became reachable. |
| 35 | [Discord: the face buttons as a voice panel](35-discord-voice-panel.md) | ✅ Done | S | Discord's face buttons as a voice panel, and what taking `Y` cost. |
| 36 | [The cloud session, and the menu that opened on top of it](36-cloud-session-menu.md) | ✅ Done | M | A gesture the game does not use reaches past an app holding the pad. |
| 37 | [The terminal: Tab, the interrupt and the scrollback](37-terminal-profile.md) | ✅ Done | S | The terminal profile: Tab, the interrupt, and the scrollback. |
| 38 | [The modifier the apps kept taking](38-profiles-in-front-of-layers.md) | ✅ Done | S | A profile stops where a modifier starts - `[bindings.*]` layers outrank it. |
| 39 | [YouTube: the television's two controls](39-youtube-controls.md) | ✅ Done | S | YouTube's two controls, on `k` rather than Space. |
| 40 | [The television's two devices, and the rows nobody could write down](40-rows-a-command-lists.md) | ✅ Done | M | A row lists its own submenu from a command, with a tick on what is in force. |
| 41 | [The pointer that kept sliding across the game](41-pointer-across-the-game.md) | ✅ Done | S | The pointer is handed over with the buttons; a stick gets no `reaches_past`. |
| 42 | [The application that opens a pad it is not played with](42-app-opens-unplayed-pad.md) | ✅ Done | S | `handover = false`, for an app that opens the pad without being played with. |
| 43 | [The game that only ever saw a keyboard](43-game-that-saw-a-keyboard.md) | ✅ Done | S | The hand-off follows the cgroup, so the game Steam started is seen as Steam's. |
| 44 | [The lock, for the game /proc argues about](44-handover-lock.md) | ✅ Done | S | The workspace lock: the hand-off answered by hand, from inside the game. |
| 45 | [Two bars along one edge](45-two-bars-one-edge.md) | ✅ Done | S | The desktop bar's state is re-said at every switch rather than once. |
| 46 | [The copy a terminal had no button for](46-terminal-copy.md) | ✅ Done | S | Copy on the terminal profile, and the row of hints that had hidden it. |
| 47 | [The badge that had never been drawn for what it carries](47-badge-for-what-it-carries.md) | ✅ Done | S | R3 redrawn - the label's fit and an inner rim; a badge is 56 by 40. |
| 48 | [The screen in front of the stream](48-screen-in-front-of-stream.md) | ✅ Done | S | `set_keeping` pins the pad ours in front of a cloud launcher that is not a game. |
| 49 | [The window that closed over a running command](49-window-over-running-command.md) | ✅ Done | S | `ZL`+`B` interrupts a running command and closes the window when there is none. |
| 50 | [The menu that was a list of verbs](50-menu-of-verbs.md) | ✅ Done | L | The menu became a HUD: head, bar, grid, legend, and the sticks. |
| 51 | [The machine, under whatever is playing](51-machine-under-what-plays.md) | ✅ Done | M | The readings page: what the machine is doing, under whatever is playing. |
| 52 | [The cell with nothing leading to it](52-cell-with-nothing-leading-to-it.md) | ✅ Done | M | A tile can go in any empty cell - a rule 50 had written down, reversed. |
| 53 | [Six sizes that are all the same size](53-six-sizes.md) | ✅ Done | M | One type and spacing ladder for the surface, on the silver ratio. |
| 54 | [A head cell that could say the time and not who you are](54-head-cell.md) | ✅ Done | M | The head cell says the time and the weather in a glyph, and not the place. |
| 55 | [A hold some hands cannot make](55-hold-some-hands-cannot-make.md) | ✅ Done | S | Every announced hold has a toggle alternative, for hands that cannot make it. |
| 56 | [The first start nobody walks to a keyboard for](56-first-start.md) | ✅ Done | S | A first run, so the accessibility settings are reachable before the pages are. |
| 57 | [A walk that never got any faster](57-walk-that-never-sped-up.md) | ✅ Done | S | A held direction accelerates instead of stepping at one rate to the last row. |
| 58 | [A machine that shut down under a resting thumb](58-shutdown-under-resting-thumb.md) | ✅ Done | S | A destructive row confirms with the announced hold, not with a plain press. |
| 59 | [The screen that never went dark](59-screen-that-never-dimmed.md) | ✅ Done | S | The inhibitor lets go, so a menu left open no longer holds the screen awake. |
| 60 | [A vocabulary with no word for going back](60-no-word-for-going-back.md) | ✅ Done | S | A fifth voice: back and cancel sound lower and softer than a confirm. |
| 61 | [A page that was swapped where it stood](61-page-swapped-where-it-stood.md) | ✅ Done | S | A transition moves in the direction of the input that caused it. |
| 62 | [A bar that came off its own edge](62-bar-off-its-own-edge.md) | ✅ Done | S | The game bar came back to its own edge, at its own width. |
| 63 | [A corner nobody could argue with](63-tile-corner-radius.md) | ✅ Done | S | The tile corner follows `decoration:rounding`, and the menu can move it. |
| 64 | [Four verbs drawn as four squares](64-four-verbs-four-squares.md) | ✅ Done | M | A card of verbs is a spine and a pointer, not four squares in a row. |
| 65 | [One line, and three drawings of it](65-one-line-three-drawings.md) | ✅ Done | S | The slider is the card of rows seen sideways: one line, three drawings of it. |
| 66 | [A hum that said nothing about the value under it](66-hum-without-a-value.md) | ✅ Done | S | The rumble tracks the value under the thumb, scaled to the current strength. |
| 67 | [The instrument, read off a Braun meter](67-braun-instrument.md) | 🗑 Removed | M | Five passes at the meter, then taken back out the same evening it landed. |
| 68 | [Three pages that were a heap of tiles](68-heap-of-tiles.md) | ✅ Done | M | Three pages of cards in bands of one height, read off the mockups. |
| 69 | [One focus, and a corner that did not fit its ring](69-focus-ring-in-the-corner.md) | ✅ Done | S | One focus figure at two sizes, and the ring's weight inside the corner radius. |
| 70 | [The arrangement behind a hold, and the axis nobody could reach](70-arrangement-behind-a-hold.md) | ✅ Done | S | Tap arranges and hold opens the guide; a cell resizes on both axes. |
| 71 | [A card that could not name what it was closing](71-card-that-could-not-name-it.md) | ✅ Done | S | The card names the window it would close, because the blur hides it. |
| 72 | [The one thing somebody wants the pad to do](72-scripts-folder-card.md) | ✅ Done | S | `System > Scripts` lists a folder, and A runs what is in it. |
| 73 | [The sentence that had nowhere to go](73-sentence-with-nowhere-to-go.md) | ✅ Done | S | Dictation can go to the clipboard instead of the cursor under it. |
| 74 | [A clock you can read from the sofa](74-clock-read-from-the-sofa.md) | ✅ Done | S | An analog clock tile: the face is furniture, the hands are geometry. |
| 75 | [The clock that could measure, and the pusher it had room for](75-clock-that-could-measure.md) | ✅ Done | M | The chronograph, a panda dial with its one pusher on A. |
| 76 | [The value a thumb could turn rather than push](76-value-a-thumb-can-turn.md) | ✅ Done | M | A knob: relative, in whole steps, and it reads a list as well as a number. |
| 77 | [A count on the bar that nothing on the page could take](77-count-on-the-bar.md) | ✅ Done | S | The waiting updates, on the bar, with the mark the drawing had. |
| 78 | [The bar that was on the wrong page](78-bar-on-the-wrong-page.md) | ✅ Done | S | Brightness moved under `Display`. |
| 79 | [Four words that never changed](79-four-words-never-changed.md) | ✅ Done | S | The legend names what the button does on the tile under the cursor. |
| 80 | [Four strokes where there was one rectangle](80-four-strokes-one-rectangle.md) | ✅ Done | S | The sliders and the checkbox became font strokes, split into parts. |
| 81 | [The page that ended in half a tile](81-page-ending-in-half-a-tile.md) | ✅ Done | S | A page ends on a whole tile, measured against the screen it is on. |
| 82 | [Somewhere for a tile to go](82-somewhere-for-a-tile-to-go.md) | ✅ Done | M | A strip along the foot holds a tile that is on no page. |
| 83 | [Pages that came to whole rows](83-pages-of-whole-rows.md) | ✅ Done | S | A page comes to whole rows - the arithmetic is the design, not a tidy-up. |
| 84 | [The dial, redrawn from a watch](84-dial-redrawn-from-a-watch.md) | ✅ Done | S | Twelve batons and a doubled twelve: the clock reads as a watch at tile size. |
| 85 | [Two menus, two buttons](85-two-menus-two-buttons.md) | ✅ Done | M | HOME opens the controller menu, PLUS a row of tiles drawn from `Console Overlay`. |
| 86 | [The page that was given out](86-now-given-out.md) | ✅ Done | S | `Now` is gone: sound to `Sound`, the lock to `Spaces`, `Start here` to `Controller`. |
| 87 | [What the couch could not reach](87-what-the-couch-could-not-reach.md) | ✅ Done | M | Night light, stay awake, screens, Bluetooth, do not disturb, network and recording on the pad; omapad's own look moved to `Controller`. |
| 88 | [A 6139, drawn in lines](88-a-6139-drawn-in-lines.md) | ✅ Done | S | The chronograph as the Seiko 6139's dial in line, to a reference drawing: double case, slim batons, one register at six. |
| 89 | [A Braun knob, drawn in lines](89-a-braun-knob.md) | ✅ Done | S | The knob as a Braun T 1000 control: knurled cap, painted index, printed scale that lights to the value. |
| 90 | [The chord is the pause](90-the-chord-is-the-pause.md) | ✅ Done | S | The workspace lock and its pair on the quick menu, and MINUS + PLUS opens the quick menu rather than the controller menu; the row trades brightness, screenshot and record for mic mute and deafen. |
