# 10. A hint bar along the bottom · Buildable · M

What the buttons do right now, in the current context, the way a console shows
it. Only what changes is worth printing: `B` Back when a menu is open, `A`
Select — and not the D-pad, which means the same thing everywhere.

**Depends on 09, and inherits its honesty problem:** the bar can only show what
*omapad* maps, not what the focused app actually does with the keystroke it
receives. For apps with a profile that is the same thing. For apps without one it
is a guess, so the bar should stay quiet rather than print a label it cannot
stand behind.
