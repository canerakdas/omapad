# 07. A console-shaped default scheme · ✅ Done · M

The default map is now console-shaped: **A** confirms (Enter), **B** goes back
(Esc), and the triggers click. Implemented in the shipped config:

| Button | Was | Now |
|---|---|---|
| `A` | Left click | Enter / confirm |
| `B` | Right click | Esc / back |
| `X` | Enter | Middle click |
| `ZR` (RT) | Window layer | Left click |
| `ZL` (LT) | Precision cursor | Right click |

**The knock-on, decided and revised:** the window layer (was `ZR`) was first put
on the left bumper **L**, but that broke the workspace flow — the user found
"cannot change workspace without L" unacceptable. So the window layer went to
**MINUS** (Xbox Back/View, the modifier the user asked for) instead:

- **L** / **R** again walk the previous / next workspace (base).
- **MINUS** (hold) opens the window layer; MINUS is the trigger so it never fires
  its own binding, and **R** moves a window between workspaces while it is open.
- **Precision removed** (`precision_button = ""`), mechanism kept in code.
- **The window layer ended up on `ZL` after all**, not MINUS. MINUS is the small
  middle button and holding it while both thumbs work the D-pad and the face
  buttons is genuinely awkward — which is the constraint that decides this:
  the modifier has to be held by a finger that is not a thumb, so it is a
  shoulder or a trigger. The bumpers walk workspaces and that was already ruled
  untouchable, so it is the left trigger. Its right click moved to **Y**, which
  was a duplicate of B (`key:ESC`) and therefore cost nothing, and the freed
  **MINUS** made the on-screen keyboard a single button instead of a
  two-handed combination.
- **Mode switching moved onto a chord**, `MINUS + PLUS` (Back + Start), which
  needed a small chord mechanism: `[chords]` in the config, completion tested
  against everything currently held so the order two thumbs land in does not
  matter, and the press taken outright — no layer opens, no partner's pending
  tap fires late. Global rather than per-layer, because the way out of game
  mode has to work from wherever you are. The HOME long-press still works.
- The **media layer dropped off MINUS** — volume/playback/brightness are parked
  for now, to be folded into the menu (item 08) rather than overload MINUS with
  a second meaning. **Done:** they are rows in the shipped menu.

**Item 03's `LT` row is settled:** `ZL`/`LT` is right-click at the base layer,
so the keyboard leaves it unbound rather than turning a held left trigger into
Shift — that would give the trigger three meanings.
