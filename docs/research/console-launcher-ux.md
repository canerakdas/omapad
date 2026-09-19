# Console-style launcher menus

**Imported, not written here.** A survey of what the four console shells do
with a pad on a television - Switch, Xbox, PS5, Steam Big Picture - with the
focus rules tvOS documents and this project's other sources do not. Dated
September 2026.

It is kept **as it was received**: the spellings, the metrics and the opinions
are its own, and rewriting a source into this project's voice is how a
quotation quietly becomes a paraphrase nobody can check. Nothing in it is
normative. A rule lives in [`../conventions/`](../conventions/); a decision
lives in [`../decisions/`](../decisions/); what is still open lives in
[`../roadmap.md`](../roadmap.md). This is the outside evidence any of them
may cite.

Most of it is about a launcher - a library, a store, a boot screen - and this
program is none of those. What transfers is everything about a pad, a focus
ring and three metres of room: §3, §4.2, §4.3, §4.5, §4.6 and §4.10. What does
not is marked as such in the pass that landed it here, and §8 is why any of it
can be argued with.

---

# Console-Style Launcher Menus: UI/UX Best Practices

**Scope:** Main menu, home screen, library, store and quick/overlay menus for a launcher / platform / storefront UI.
**Target:** Gamepad-only input on a TV or large display (10‑foot / lean‑back context).
**Reference platforms:** Nintendo Switch / Switch 2, Xbox Series (2023–2026 Home + Guide), PlayStation 5, Steam Big Picture (Steam Deck UI, incl. Sept 2026 beta), plus lessons from Apple tvOS.
**Last researched:** September 2026.

---

## 0. Assumptions & decisions made while writing this

These are the choices that shape the whole document. Flag any that are wrong.

1. **Gamepad-only.** Mouse mode, touch and remote-control input are out of scope. Keyboard/mouse fallback is mentioned only where a platform's mistake is instructive.
2. **Launcher, not game.** The document covers launching, browsing, buying and system-level tasks — not in-game pause menus or HUDs.
3. **"Best practice" = observed convergence + documented platform guidance.** Where the four platforms disagree, the disagreement is stated rather than resolved by opinion.
4. **Simplicity is weighted heavily.** Each recommendation notes the complexity cost where it matters. Several "nice" features (widgets, themes, ads) are deliberately marked as optional or discouraged.
5. **Numbers are guidance, not law.** Microsoft's 10‑foot metrics are the most concrete published source, so they anchor the sizing section; others are approximations.

---

## 1. Core principles (the "why" behind every rule)

| # | Principle | One-line rationale |
|---|-----------|--------------------|
| P1 | **Time-to-game is the primary metric.** | Every platform that succeeded (Switch, Steam Deck UI) optimized for "press one button, be in the game." Every platform that got criticized (Xbox 2022 Home test, PS5 trophies) added steps or clutter between the player and play. |
| P2 | **Focus is the cursor.** | With D‑pad/stick navigation there is no pointer. If the user glances away and back, they must instantly know where focus is and where it can go next. |
| P3 | **Two layers, never three.** | Home (browse/launch) + an overlay/quick menu (in-game, system tasks). Everything else is a leaf screen one press away from either. Deeper hierarchies are where all four platforms' complaints cluster. |
| P4 | **Low density, big targets.** | Information on screen should be comparable to a phone screen, not a desktop. Roughly 2.5–3× mobile type sizes. |
| P5 | **Speed is a feature, not polish.** | Users tolerate a sparse UI if it is instant; they do not tolerate a rich UI that lags. |
| P6 | **Consistency of input mapping beats cleverness.** | A = select, B = back, bumpers = tabs, Y = search/context, hold = destructive/confirm. Any deviation costs learnability across every screen. |
| P7 | **Hero art is the personality.** | Consoles increasingly let the selected game's artwork own the screen (PS5, Xbox 2023, Steam Big Art Mode 2026). Chrome gets out of the way. |
| P8 | **Monetization surfaces are a tax on trust.** | Ads/upsell tiles are the most consistent source of negative feedback on Xbox and PS5 Home. Steam's ad-free home is repeatedly cited as a differentiator. |

---

## 2. Platform teardowns

Each teardown covers: structure → what works → what to avoid → transferable pattern.

### 2.1 Nintendo Switch / Switch 2

**Structure**
- Single-screen Home: user avatars (top-left), one horizontal row of recently played titles (fixed cap, then an "All Software" tile), a bottom row of system icons (News, eShop, Album, Controllers, Settings, Sleep; Switch 2 adds GameChat "C", GameShare, Virtual Game Cards).
- Hold HOME → Quick Settings overlay (brightness, sleep, airplane mode, volume). Not a full guide — deliberately tiny.
- Themes: only Basic Light / Basic Dark, even on Switch 2 at launch. Rounded corners and a multi-colored focus outline were the visible Switch 2 refinements.
- Joy‑Con 2 can act as a mouse on Home, but Nintendo kept the layout D‑pad-first; the mouse adds nothing the D‑pad can't do.

**What works**
- **Instant.** Cold boot ~10s, wake-from-sleep near-instant, every transition rapid. Speed reinforces the perception of simplicity.
- **One layer, no scrolling on Home.** Everything you can do is visible; nothing hides below the fold.
- **Over-scaled UI** that reads from the couch and stays usable on a 7" screen — a single layout across both.
- **Minimal text, medium-weight type, high contrast.** Nintendo shipped without a text-size setting because the baseline is already large.
- **Speed after the Wii U:** Nintendo explicitly kept Home free of clutter to protect responsiveness.

**What to avoid / criticisms**
- Almost no personalization (themes, folders on Home) for 8+ years; folders exist only inside the library. Users feel the UI is "sterile."
- Discovery is weak: the recent-row cap hides owned games; users report forgetting titles they own.
- Design has stalled across a hardware generation — iteration without evolution reads as neglect.

**Transferable pattern**
> A single non-scrolling Home with a capped "recent" row + one library entry point + a system row is the minimum viable launcher, and it is *enough* if it is instant.

### 2.2 Xbox Series X|S (Home + Guide, 2023–2026)

**Structure**
- **Home:** quick-access strip at the top (Store, Game Pass, My Games & Apps, Settings…), a large gap that shows the background/theme, then a "Jump back in" row of recent titles, then pinnable "groups" and curated rows further down. Since April 2026: up to ten pinnable Home groups, custom UI accent colours, Quick Resume management, profile badges.
- **Guide:** press the Xbox button anywhere → a tabbed side overlay (Home shortcuts, Parties & chats, Achievements, Captures, Profile & system…). Tabs switch with **bumpers/triggers**. Hold the Xbox button → power/hardware menu.
- Focus on a tile swaps the background to that game's art ("responsive game art").
- 2026 direction: a unified UI across console, PC, handheld and cloud, with **fewer ad slots**, profile moved to the top-right, flatter/rounded visual language.

**What works**
- **The Guide is the best-in-class overlay.** Bumper/trigger tab switching is fast, muscle-memory-friendly, and reachable from any state (dashboard, in-game, store). PS5's Control Center is widely described as a descendant of it.
- **Y = search** is a platform-wide accelerator with a visual glyph hint.
- **"Jump back in" + Quick Resume** collapses time-to-game to one press on the most likely intent.
- **Published 10‑foot metrics** (see §4) give teams hard numbers.
- Microsoft ran an 8-month Insider experiment (Sept 2022 → 2023), pulled a variant that "felt crowded," and reshipped. Iterating in public with a feedback loop is a process best practice.

**What to avoid / criticisms**
- The 2022 Home prototype put a 12-tile Game Pass block and a "Join Game Pass" tile in the primary viewport → read as "a giant Game Pass ad," and Microsoft admitted it crowded out the user's background.
- Tile grid density is still higher than PS5/Switch; users repeatedly ask for smaller/hideable tiles and an "alphabetical list + black background" mode.
- Fragmentation between console (still "Metro"-derived) and PC/cloud UIs — now being fixed, but a cautionary tale for multi-surface products.

**Transferable pattern**
> Overlay guide with L/R tab switching + a single hero background driven by focused game art + a "Jump back in" row as the first focusable element.

### 2.3 PlayStation 5

**Structure**
- **Home:** top bar switches **Games / Media** (and in the April 2026 beta, separate tabs for PS Store, PS Plus, Games, Library, switched with L1/R1). Below: one horizontal row of recent titles (fewer slots than PS4 — ~8 plus Library), with the focused game's art and a **Game Hub** (Activities, news, trophies, friends playing) filling the rest of the screen.
- **Control Center:** press PS button in-game → bottom-anchored quick bar (Home, Switcher, Friends, Mic, Sound, Power…) plus a row of context **cards** (current Activity, trophies, screenshots, game help, party). Cards are weighted per game/session.
- **Welcome Hub** (2024→): a home tile that opens a widget canvas (storage, controller battery, friends online, trophies, recently played with playtime) with resizable widgets, preset layouts, custom or animated backgrounds, and an idle **Showcase Mode** that hides widgets to show the background full-screen.
- Rounded cards everywhere; light-weight type; subtle ambient particle motion.

**What works**
- **System-to-game integration:** the Home shows *what you were doing* (Activity cards, progress, what's new since last session), not just *what you own*. This is the strongest "resume intent" model of the four.
- **Control Center quick toggles** (audio output switching, system mute, mic) are praised as fast in-game system control.
- **Idle behaviour** (Showcase Mode → later Steam's screensavers) turns an idle launcher into ambient art rather than a static grid.
- Splitting store/plus/library into L1/R1 tabs (2026) explicitly reduces horizontal scrolling — a small structural fix that "means less clicking."

**What to avoid / criticisms**
- **Two places to be** (Home vs Control Center) confused users at launch; some tasks got *longer*. Trophies are the canonical example: PS4 quick menu showed a vertical list in-game; PS5 shows ~8 truncated cards and then kicks you out of the game into the system trophy menu, which doesn't even preselect the current game.
- Cards truncate text; horizontal card strips are poor for scanning long lists — vertical lists scan faster from the couch.
- No bumper/trigger navigation in Control Center at launch (Xbox has it in the Guide).
- Themes/folders were absent for years; the Welcome Hub is a partial substitute and adds complexity.
- The Store/Plus tiles competing for the top bar with games — the 2026 beta explicitly shrinks their share.

**Transferable pattern**
> Contextual cards that describe *state* (what to resume, what changed) are powerful — but keep a fast, complete, vertical list behind them so cards never become the only path.

### 2.4 Steam Big Picture (Steam Deck UI, Feb 2023 → Sept 2026)

**Structure**
- The Steam Deck "Gaming Mode" UI replaced the 2012 Big Picture Mode on desktop in Feb 2023. The old one was blurry, capped at 1080p, and had tabs that "straight-up don't work."
- **Steam/Guide button** → main menu: Home, Library, Store, Friends & Chat, Media, Downloads, Settings, Power. This *is* the top-level navigation; it isn't parked on screen.
- **Quick Access Menu (… button)** → side panel with notifications, friends, quick settings (brightness, volume, performance overlay), tabbed with bumpers.
- **Universal search** across Library, Store and Friends from one field.
- **Library:** collections (user-defined), filters (installed, "Great on Deck," compatibility), Favorites surfaced first. Tabs across the top switched with bumpers.
- **Home** (Sept 2026 beta): optional **Big Art Mode** lowers the recent-games carousel and splashes the focused game's art across the backdrop; a **Personal Calendar** of upcoming releases sits in a "Recommended" tab; **screensavers** (art slideshow from recent games/screenshots, bouncing logo, or custom) with a configurable idle timer.
- Confirmation dialogs before switching to desktop / exiting VR now warn explicitly if an active game will be closed. Sleep no longer asks.
- Accessibility → UI scaling, colour filters, per-game controller remapping.

**What works**
- **Library organization is the deepest of the four** (collections + filters + favorites) — a launcher that must handle thousands of titles needs this.
- **No ads on Home.** Repeatedly named as a reason users prefer it.
- **Hardware-agnostic UI** designed to scale from a 7" panel to a 65" TV; hides the cursor in gamepad mode.
- **Big Art Mode** is a small change with an outsized effect: same content, moved "below the fold," giving the focused game the screen — a good example of a *layout mode toggle* rather than a redesign.
- Long-press the Steam/QAM button shows a **shortcut reference card**: discoverability for chords without cluttering the UI.

**What to avoid / criticisms**
- The **controller configurator** was designed for the Deck's 7" screen and ported to TV without re-layout; long-time users called it "not ready for BPM." Lesson: an overlay that's fine on a handheld can be the wrong shape on a TV.
- Focus-order bugs in nested filter panels (visual position ≠ logical order) trapped users — a classic XY-navigation failure.
- Early desktop rollout suffered black screens, controller-input breakage and lag; and prompts still said "Steam Deck" on PC. Ship copy and states per surface.
- Steam's desktop Store pages, when reached from Big Picture, are dense web content that's hard to read from the couch.

**Transferable pattern**
> Top-level nav lives behind one system button; a second button owns quick settings; search is universal; library gets real filtering; the home layout is a user-selectable mode.

---

## 3. What to learn from Apple (tvOS)

Apple never shipped a game launcher, but tvOS has the most rigorously documented *focus system* for a lean-back, controller-driven UI. Transferable lessons:

1. **Focus is communicated with scale + depth, not just a border.** tvOS enlarges the focused item and applies a subtle parallax tilt that follows the input surface. Shadows are exaggerated because they read from a distance. Provide larger assets for the focused size so nothing looks soft.
2. **Rely on a system-wide focus engine; don't rebuild it per screen.** Apple's guidance is blunt: build a custom focus system only if absolutely necessary. Inertia is part of it — fast swipes accelerate/decelerate focus through items, so long rows feel navigable.
3. **Every screen has a default focused element** — the most likely intent (usually the first primary content item). Never present a screen with nothing focused.
4. **Preserve focus memory.** Returning to a screen restores the previously focused item, not the first.
5. **Menu/Back always goes up exactly one level**, and from the top level exits the app. No exceptions, no "back closes a modal *and* pops a screen."
6. **Focus targets are big.** Apple recommends roughly 250×150pt minimum for cards; small actions are grouped under a focused parent rather than being independently focusable.
7. **Focused ≠ highlighted ≠ selected.** Design up to five visually distinct states (normal, focused, highlighted/pressed, selected, disabled).
8. **Top Shelf idea:** when an app icon is focused on the tvOS Home, a large banner above shows that app's featured content. Consoles adopted the equivalent: focusing a game shows its hub/art. Use the *focused item to drive the hero area* rather than dedicating a permanent hero slot.
9. **No cursor. Ever.** If a pointer appears in a gamepad flow, treat it as a bug (Steam hides it explicitly).
10. **Motion is restrained and non-fixed-duration.** Focus animations are coordinated with the focus engine's timing rather than hard-coded, so rapid input never queues a backlog of animations.

---

## 4. Best practices by topic

### 4.1 Information architecture

- **Home = launch + resume.** First focusable element on boot is the most recently played game (Xbox "Jump back in," Switch first tile, PS5 first tile, Steam carousel). Launching should be one A-press from the boot screen.
- **Two navigation layers only:**
  1. *Home / Library / Store / Friends / Settings* (top level).
  2. *Overlay (Guide / Control Center / Quick Access)* reachable from anywhere.
  Every other screen is a leaf. If a task needs three transitions, redesign it (PS5 trophies).
- **Top level lives behind one hardware button** (Steam button / Xbox button / PS button), *or* as a persistent top bar with L/R tab switching (PS5 2026, Steam Library). Pick one; don't do both.
- **Cap the recent row** (Switch ~12, PS5 ~8) and give it a clear "All games / Library" terminator tile. Don't make the row infinite.
- **Library must scale.** Alphabetical list view, collections, filters (installed / not installed, genre, controller support, recently added), favorites pinned. This is Steam's clear advantage and Switch's clear gap.
- **Store is a separate tab, not Home content.** Recommendations may appear on Home *below the fold* (Steam's Recommended tab, Xbox's curated rows) but not in the primary viewport. See §4.8.

### 4.2 Focus & navigation model

- **XY (grid) navigation only.** Everything focusable must be reachable with up/down/left/right; no element may require a pointer.
- **Visual order = logical order.** The Steam filter-panel bug (dropdown visually at the bottom, logically at the top) is the failure case. Test with narration on.
- **Default focus on every screen**; **restore focus** on return; **no focus traps** in modals (B always closes).
- **Wrap linear menus** (last → first) but *don't* wrap 2D grids — wrapping a grid makes spatial position unpredictable.
- **Edge-to-edge in ≤ 6 presses** (Microsoft's rule of thumb). If a row needs more, add a jump control (bumpers page, triggers jump to start/end) or reduce items.
- **Fixed focus, moving content** for long rows/carousels: keep the focused item in a stable screen position and scroll content under it. Reduces eye travel.
- **Focus visual must survive a glance away.** Combine at least two cues from: scale, outline, glow/shadow, background swap, colour shift. Outline alone is insufficient at 10 ft; scale alone breaks in dense grids.
- **Focus animation ≤ ~150 ms** and interruptible; queued animations on rapid stick input are a common source of "the menu feels laggy."
- **Analog stick + D‑pad both navigate**, with stick auto-repeat and acceleration on hold.

### 4.3 Input mapping conventions (Xbox layout; map equivalently on other pads)

| Input | Convention | Notes |
|-------|-----------|-------|
| **A / Cross** | Select / confirm | Never overload with "options." |
| **B / Circle** | Back one level; close overlay/modal | From Home, B does nothing (or returns to first tile). Never exit the app on B. |
| **X / Square** | Secondary action (e.g., filter, options on Steam library) | Show a glyph hint. |
| **Y / Triangle** | Search (Xbox convention) or context menu (Steam) | Choose one platform-wide meaning; show glyph. |
| **LB/RB** | Switch tabs / categories | Xbox Guide, Steam, PS5 2026 all converge here. |
| **LT/RT** | Page / jump, or secondary tab level | Xbox uses triggers for the Guide's outer tabs. |
| **Menu / Options (≡)** | Context menu for the focused item | Manage / uninstall / pin / details. |
| **View / Share** | Open nav pane or capture | Microsoft suggests View opens the nav pane on TV. |
| **Guide / Home button — tap** | Overlay (Guide / Control Center / main menu) | Must work from *any* state, including inside a game. |
| **Guide / Home — hold** | Power / hardware menu (Xbox, Steam) or Quick Settings (Switch) | Keep hold ≥ ~700 ms to avoid accidental triggers. |
| **Hold A** | Confirm destructive / irreversible actions | Delete, uninstall, sign-out, power off. |
| **Long-press system button** | Shortcut reference card (Steam) | Cheap discoverability for chords. |

- **Always show button glyphs** for available actions in a bottom-anchored legend, using the *connected controller's* glyph set (Steam even lets users swap glyph sets). Never show "Press Steam Deck…" copy on a TV build.
- **Never require chords** for primary flows; chords are accelerators only.

### 4.4 Overlay / quick menu (Guide, Control Center, QAM)

- **One button, from anywhere, ~instant.** Opening must not depend on the game's state.
- **Tabbed, bumper-switched, side- or bottom-anchored**; leave most of the game visible behind (Xbox side panel, PS5 bottom bar).
- **Contents, in priority order:** resume/switch game · friends & party/voice · notifications · captures · quick settings (audio output, mic, brightness, network, performance) · power.
- **Quick settings are toggles/sliders, not deep links.** PS5's audio-output switcher is the praised model.
- **Do not make the overlay the only route to a full list.** Keep a complete vertical list (e.g., all achievements/trophies for the current game) reachable *inside* the overlay; the PS5 card-strip-then-eject pattern is the anti-example.
- **Confirmations only when a game would be lost.** Steam's 2026 change: warn on actions that close a running game; remove the prompt for sleep. Mirror that.
- **Design the overlay for the TV first if you also ship a handheld** — Steam's controller configurator is the cautionary case.

### 4.5 Visual design for 10‑foot viewing

Anchored on Microsoft's published Xbox/TV numbers (1080p canvas, 200 % scale → 960×540 "effective pixels," epx), cross-checked against Android TV and Apple guidance.

| Topic | Guidance |
|-------|----------|
| **Density** | Phone-like, not desktop-like. Roughly 5–8 primary tiles across; one hero area; ≤ 3 rows visible. |
| **Interactive target height** | ≥ 32 epx (≈ 64 px at 1080p). Apple: ~250×150 pt for cards. |
| **Body text** | ≥ 15 epx (≈ 30 px @1080p, ≈ 24 sp Android TV). Supplemental ≥ 12 epx. Multiply mobile sizes by ~2.5–3×. |
| **Safe area** | Keep essential UI ≥ 5 % from edges: 27 epx top/bottom, 48 epx left/right at 960×540 (≈ 54 / 96 px @1080p). Backgrounds and scrolling lists may bleed to the edge; the *focused* item and its focus visual must stay inside the safe area. |
| **Contrast** | ≥ 4.5:1 for text (WCAG AA / XAG 102). Text is its own layer over art with a scrim; never bake text into images (breaks narration and contrast). |
| **Colour** | Dark theme default (media context; Xbox defaults dark). Avoid subtle hue differences carrying meaning — TVs vary wildly. Historic "TV‑safe" range RGB 16–235; modern consoles remap automatically, but avoid pure #000/#FFF for large fields (blooming/banding). |
| **Hero art** | Focused game's key art drives the background (PS5, Xbox 2023, Steam Big Art). Chrome is translucent/dark over it. Require key-art assets in ≥ 2 aspect ratios (16:9 hero, portrait/square capsule). |
| **Corner radius & shape** | All four platforms converged on rounded tiles/cards (Switch 2, PS5, Xbox 2026, Steam). |
| **Tooltips** | Avoid; they appear on focus delay and become noise. Put labels beside icons permanently (Microsoft: CommandBar labels to the right of icons). |
| **Text volume** | Users don't read paragraphs on TV. One line of description on Home; full text only on the detail page. |
| **Idle state** | After N minutes idle, dim chrome and show art (PS5 Showcase Mode, Steam screensavers). Protects OLEDs and looks intentional. |

### 4.6 Motion, sound, feedback

- **Every focus move gets an audible tick; every confirm gets a distinct sound**; cancels/back get a lower/softer sound. Microsoft auto-enables control sounds on Xbox for this reason.
- Transitions are **rapid** (Switch: "every UI transition is rapid") and **directional** (content moves in the direction of the input).
- **Ambient motion is subtle** (PS5 particles, tvOS parallax) and must respect a reduce-motion setting.
- **Loading states**: prefer skeleton/placeholder tiles over spinners; never block focus on a partially loaded Home.
- **Haptics** (if supported): light tick on focus, stronger on confirm — optional, off by default on TV pads that lack it.

### 4.7 Performance budgets

- **Boot to interactive Home:** target ≤ 10 s cold (Switch benchmark); wake from sleep: near-instant.
- **Overlay open:** ≤ 250 ms perceived.
- **Focus response:** ≤ 1 frame input latency for focus move; art swap can lag by 100–200 ms with crossfade.
- **Never** let store/recommendation fetches delay rendering the recent row — render local data first, hydrate remote later.
- Instrument these; the Xbox 2026 rework and every Steam client note lead with "startup performance improved," because users notice.

### 4.8 Store, discovery, and monetization placement

- **Above the fold on Home: the user's own content only.** Recent games, library entry, friends. This is the single most consistent user demand across Xbox and PS5 feedback threads.
- **Discovery goes in its own tab or below the fold** (Steam "Recommended" + Personal Calendar; Xbox curated rows lower on Home; PS5 shrinking Store/Plus tiles in 2026).
- **If you must show promotions on Home:** ≤ 1 slot, clearly labelled, user-dismissible/hideable, never the default focus. Xbox's 2026 direction explicitly reduces ad slots after years of complaints.
- **Store pages must be re-laid-out for TV** — no reused web density (Steam's weak spot).
- **Wishlist / sale signals** can live on the Library tile as a badge (Xbox "My games & apps" attention badge) rather than as a tile of their own.

### 4.9 Personalization (optional — weigh complexity)

Ranked by value-to-complexity:

1. **Accent colour** (Xbox 2026). Cheap; big perceived ownership.
2. **Background: own screenshot or game art** (PS5 Welcome Hub, Steam screensavers). Cheap if the capture pipeline exists.
3. **Pin / reorder Home groups or favorites** (Xbox groups, Steam favorites/collections). Medium; requires a "manage" mode with clear glyphs.
4. **Light/dark** (Switch). Cheap; near-mandatory.
5. **Widgets canvas** (PS5 Welcome Hub). Expensive; only justified if you have real-time data worth glancing at (friends online, downloads, battery). Not recommended for v1.
6. **Full themes with sounds/icons** (3DS/PS4 era). Expensive and rarely maintained; both Sony and Nintendo dropped them.

### 4.10 Accessibility (baseline, not optional)

Drawn from Xbox Accessibility Guidelines (XAG 101/102/106/112) and platform features:

- **Screen narration** for every focusable element: label, control type, state, position ("3 of 12"). Decorative graphics are not announced. Focus order matches meaning.
- **UI scale** setting (Steam) and **text size** setting; layouts must reflow at ≥ 150–200 %.
- **High-contrast mode** and **colour filters** (Xbox, Steam).
- **Reduce motion** toggle that disables parallax/ambient animation.
- **Button remapping** system-wide; **hold-to-press → toggle** alternative for hold-confirm actions.
- **No time-limited menus** (auto-dismissing prompts must be pausable/re-openable).
- **Accessibility settings reachable from the first-run flow** and from the overlay, and readable by narration before the user configures anything.
- **Never encode meaning in colour alone** (e.g., "installed" = green badge → add icon/text).

### 4.11 Search and text entry

- **Universal search** (Steam) across library + store + friends from one entry point, bound to a single button (Y) with a visible glyph.
- **On-screen keyboard opens already visible** when search is invoked; results filter as you type (don't require "submit").
- **Prefer selection over typing** everywhere else: filters, presets, recent queries, alphabet jump-bars.
- **Companion-phone or voice input** is a nice-to-have, not a substitute for a good OSK.

### 4.12 Multi-user & social (brief)

- User picker at boot if > 1 profile (Switch avatars, Xbox profile top-right in 2026 direction).
- Friends/party lives in the overlay, not on Home's primary viewport; "friends playing X" can decorate a game tile (PS5, Xbox).
- Invites are notifications that deep-link to a join action; joining should be ≤ 2 presses.

---

## 5. Anti-patterns (observed failures, in one place)

| Anti-pattern | Where seen | Why it hurts |
|--------------|-----------|--------------|
| Promotional tiles in the primary viewport | Xbox 2022 Home test, PS5 Store/Plus tiles | Reads as ads; buries the user's own content; Microsoft rolled it back |
| Overlay card strip as the *only* path to a full list | PS5 trophies | Truncated cards + ejection from the game = more steps than last gen |
| Visual order ≠ focus order | Steam filter panels | Users "can't reach" controls; narration reads wrong |
| Overlay designed for a 7" screen shipped to TV unchanged | Steam controller configurator | Too dense, wrong hit-targets, feels "half-baked" |
| Surface-specific copy leaking across surfaces | "Steam Deck" prompts on PC Big Picture | Erodes trust in polish |
| Dense reused web content on TV | Steam Store pages in Big Picture | Illegible from the couch |
| Zero personalization for a full generation | Switch | Users describe the UI as sterile even when it's fast |
| Capped recent row with no discoverable "all" path | Switch | Users forget what they own |
| Tooltips on focus | UWP default on Xbox | Noise; appear/disappear constantly during navigation |
| Confirmations on every power action | Steam pre‑2026 (sleep) | Friction; Steam removed the sleep prompt and kept only game-loss warnings |
| A cursor in a gamepad flow | Old Big Picture | Signals "this wasn't designed for you" |

---

## 6. Design checklist (copy into your review template)

**Structure**
- [ ] First focusable element on boot is the most recently played game; one A-press launches it.
- [ ] Exactly two navigation layers (top-level + overlay); every other screen is a leaf.
- [ ] Recent row is capped and ends in a Library tile.
- [ ] Library has list view, filters, collections/favorites, alphabetical jump.
- [ ] Store/recommendations are not in Home's primary viewport.

**Focus & input**
- [ ] Every screen has a default focus; focus is restored on return.
- [ ] Visual order == focus order (verified with narration).
- [ ] No focus traps; B closes any modal.
- [ ] Edge-to-edge ≤ 6 presses or bumpers/triggers provide jumps.
- [ ] Focus visual uses ≥ 2 cues and stays inside the safe area.
- [ ] A/B/X/Y/LB/RB/LT/RT/Menu/View meanings are consistent on every screen and shown as glyphs.
- [ ] Destructive actions require hold or explicit confirm; only actions that lose game state prompt.
- [ ] No cursor appears anywhere in gamepad mode.

**10‑foot visuals**
- [ ] Body text ≥ 15 epx (≈ 30 px @1080p); targets ≥ 32 epx tall.
- [ ] Essential UI inside 5 % safe area; art may bleed.
- [ ] Text contrast ≥ 4.5:1 with scrim over art; no text baked into images.
- [ ] Dark theme default; no pure white large fields.
- [ ] Focused game art drives the hero/background.
- [ ] Idle state dims chrome / shows art.

**Feedback & performance**
- [ ] Focus tick, confirm and back sounds; reduce-motion respected.
- [ ] Cold boot ≤ 10 s to interactive; overlay ≤ 250 ms; local data renders before remote.

**Accessibility**
- [ ] Full narration; UI scale; high-contrast; colour filters; remapping; hold→toggle.
- [ ] Accessibility settings reachable from first run and from the overlay.

**Process**
- [ ] Tested on a real 55"+ TV from ~3 m with a gamepad only.
- [ ] Per-surface copy and layouts if you ship more than one form factor.
- [ ] A public/insider feedback loop before shipping Home changes.

---

## 7. Open decisions this document cannot make for you

These are the points where the platforms diverge or where your product context decides. Each is worth a deliberate call:

1. **Top-level nav: hidden behind a system button (Steam) or a persistent L/R-tabbed top bar (PS5 2026)?** The button approach maximizes art space; the bar maximizes discoverability for new users.
2. **How big is the library you must support?** < 50 titles → Switch-style Home is enough. Thousands → Steam-style collections/filters are mandatory on day one.
3. **Does the launcher run *over* games (Guide/Control Center) or only *between* them?** This determines whether the overlay exists at all — and it's the most expensive component.
4. **Is there a store?** If yes, the placement rules in §4.8 will be contested by business stakeholders; decide the policy before design, not after.
5. **Will a handheld or PC surface ever exist?** If yes, design the TV overlay first and adapt down; the reverse (Steam's configurator) failed.
6. **Personalization depth for v1:** accent colour + background is the recommended floor; widgets are the recommended ceiling to *defer*.

---

## 8. Sources

Platform documentation and first-party posts
- Microsoft Learn — *Designing for Xbox and TV* (10‑foot metrics, safe area, scale, focus, nav pane, search): https://learn.microsoft.com/en-us/windows/apps/design/devices/designing-for-tv
- Microsoft Learn — *Xbox Accessibility Guidelines* 101 (Text), 102 (Contrast), 106 (Screen narration), 112 (UI navigation): https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/112
- Xbox Wire — *Your Feedback Shapes the New Home Experience* (May 2023): https://news.xbox.com/en-us/2023/05/01/xbox-insiders-your-feedback-shapes-the-new-home-experience/
- PlayStation Blog — *First look: PS5's next-generation user experience* (Oct 2020): https://blog.playstation.com/2020/10/15/first-look-playstation-5s-next-generation-user-experience/
- PlayStation Blog — *PS5 system update adds Welcome hub…* (Sept 2024): https://blog.playstation.com/2024/09/12/ps5-system-update-adds-welcome-hub-party-share-personalized-3d-audio-profiles-adaptive-controller-charging-and-more/
- PlayStation Support — *System software update features for PS5*: https://www.playstation.com/en-us/support/hardware/ps5/system-software-info/
- Apple Developer — *Human Interface Guidelines: Focus and selection*: https://developer.apple.com/design/human-interface-guidelines/focus-and-selection
- Apple Developer — *App Programming Guide for tvOS: Creating Layered Images*: https://developer.apple.com/library/tvos/documentation/General/Conceptual/AppleTV_PG/CreatingParallaxArtwork.html
- Amazon — *Fire TV Design and User Experience Guidelines*: https://developer.amazon.com/docs/fire-tv/design-and-user-experience-guidelines.html

Xbox (2023–2026)
- Digital Trends — *All Xbox home screens are getting a PS5-style makeover* (Jul 2023): https://www.digitaltrends.com/gaming/xbox-home-interface-redesign-2023/
- Pure Xbox — *Xbox Unveils New Home UI For 2023* (Sept 2022): https://www.purexbox.com/news/2022/09/xbox-unveils-new-home-ui-for-2023-and-your-feedback-is-wanted
- Pure Xbox — *Xbox's New Dashboard Update Is Now Available For All Users* (Apr 2026): https://www.purexbox.com/news/2026/04/xboxs-new-dashboard-update-is-now-available-for-all-users
- Windows Report — *Xbox May Have Just Teased a New Dashboard UI…* (May 2026): https://windowsreport.com/xbox-may-have-just-teased-a-new-dashboard-ui-for-a-more-consistent-experience-across-devices/
- HotHardware — *New Xbox Dashboard Mockup Hints at Potential UI Overhaul for 2026*: https://hothardware.com/news/new-xbox-dashboard-mockup

PlayStation 5
- EGM — *The good and bad of the PlayStation 5's user experience*: https://egmnow.com/the-good-and-bad-of-the-playstation-5s-user-experience/
- Pixelrater — *PS5 Has a UX and UI Problem*: https://pixelrater.com/ps5-has-a-ux-and-ui-problem/
- whatbrentsay — *PlayStation 5 UI reveal: observations from a designer*: https://old.whatbrentsay.com/2020/10/21/playstation-5-ui-reveal-observations-from-a-designer/
- PlayStation LifeStyle — *PS5 Update for April 2026 Stealth Drops UI Redesign*: https://www.playstationlifestyle.net/2026/04/06/ps5-update-april-2026-ui-redesign/
- Playfront — *Sony is testing a new UI design for the home menu* (Apr 2026): https://playfront.de/en/ps5-ps5-pro-system-update-sony-testet-neues-ui-design-fuer-das-home-menue/
- Screen Rant — *PS5 Update With More Home Screen Customization* (Nov 2025): https://screenrant.com/playstation-5-system-update-new-features/

Nintendo Switch / Switch 2
- Charlie Deets — *Thoughts on the Nintendo Switch User Interface* (2017): https://medium.com/@charliedeets/thoughts-on-the-nintendo-switch-user-interface-b441129f063d
- GameSpot — *Switch 2's Main Menu Isn't That Different…* (Apr 2025): https://www.gamespot.com/articles/switch-2s-main-menu-isnt-that-different-from-the-one-on-nintendo-switch/1100-6530604/
- Game Rant — *Nintendo Switch 2 May Have Dropped The Ball in One Key Area* (Apr 2025): https://gamerant.com/nintendo-switch-2-ui-simple-few-changes-bad-why/
- TechRadar — *Joy-Con 2 mouse controls can be used to navigate the Home Menu*: https://www.techradar.com/gaming/the-nintendo-switch-2-joy-con-2-mouse-controls-can-be-used-to-navigate-the-home-menu
- Notebookcheck — *Switch 2 leaks reveal only light and dark mode themes*: https://www.notebookcheck.net/Nintendo-Switch-2-leaks-reveal-only-light-and-dark-mode-themes-but-more-customization-could-arrive.1026296.0.html

Steam Big Picture / Steam Deck UI
- PC Gamer — *At long last, the Steam Deck UI has replaced Steam's Big Picture mode* (Feb 2023): https://www.pcgamer.com/at-long-last-the-steam-deck-ui-has-replaced-steams-big-picture-mode/
- KitGuru — *Steam Deck UI finally comes to Big Picture mode on PC* (patch-note highlights): https://www.kitguru.net/gaming/mustafa-mahmoud/steam-deck-ui-finally-comes-to-big-picture-mode-on-pc/
- Steam Community — *The new gamepad configuration UI is NOT ready for BPM* (Oct 2022): https://steamcommunity.com/groups/SteamClientBeta/discussions/3/3461605794221825896
- GamingOnLinux — *Steam Beta for Sept 9th has huge changes – Big Art Mode, Screensaver…* (Sept 2026): https://www.gamingonlinux.com/2026/09/steam-beta-for-sept-9th-has-huge-changes-big-art-mode-screensaver-proton-option-changes-desktop-mode-toggle-for-steamos/
- PC Gamer — *Steam's latest beta brings 'Big Art' to Big Picture Mode…* (Sept 2026): https://www.pcgamer.com/games/steams-latest-beta-brings-big-art-to-big-picture-mode-and-steam-deck-and-customizable-screensavers-too/
- Digital Citizen — *Steam Deck Beta Update Adds Big Art Mode, Screensavers and Desktop Boot Option* (Sept 2026): https://www.digitalcitizen.life/steam-deck-beta-update-adds-big-art-mode-screensavers-and-desktop-boot-option/
- decky.net — *Steam Deck Buttons explained*: https://decky.net/en/blogs/news-en/steam-deck-buttons-explained

General 10‑foot UI
- Toptal — *Rethinking User Interface Design for the TV Platform*: https://www.toptal.com/designers/ui/tv-ui-design
- Purrweb — *How to Create a Smart TV UI Design* (type-size and safe-zone numbers): https://www.purrweb.com/blog/how-to-design-an-app-for-smart-tvs/
- Solid Digital — *Designing for the 10-Foot User Experience*: https://www.soliddigital.com/blog/designing-10-foot-user-experience
