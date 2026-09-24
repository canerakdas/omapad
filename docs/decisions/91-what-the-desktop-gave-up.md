# 91. What the desktop gave up · ✅ Done · S

Asked for from the sofa: *blur hyperlandda default kapaliymis, bu sebeple
calismiyor diger makinede* - blur is off by default, which is why it does not
work on the other machine. Then, once the reason was known: *omapad hic
bakmasin default os neyse onu uygulasin, ekstradan blur eklemesin kendi* -
omapad should not look at it at all; whatever the OS does is what applies,
and omapad adds no blur of its own.

**Hyprland was not the one that turned it off.** Hyprland's own default for
`decoration.blur.enabled` is on. Omarchy's `default/hypr/looknfeel.lua` sets
it off, since `935283c8` ("Simplify rendering", 2026-07-13), with the reason
in the commit: *it's adding so little visual flair and is a source of GPU
load*. Shadows went in the same commit. A machine installed after that, or
one without its own `looknfeel.lua` saying otherwise, has no blur anywhere,
and the layer rule omapad asked for was a no-op there - which was the menu
that looked plainer on the other machine.

**So omapad no longer asks for a blur at all.** `[ui] blur`, `blur_rule` and
`blur_alpha` are gone, and with them `apply_blur`, the Hyprland `/eval` it
went through, and `compositor_stamp` - which watched `~/.config/hypr` only so
the rule could be asked for again after a reload threw it away. With no rule
of ours to lose, a reload takes nothing, and `check_theme` is left with the
pointer, which a theme change still has to redraw. An old user config that
still says `blur = true` loads; the key is simply not read.

`[menu] dim` carries the contrast, as it already did wherever blur was off.
Blur behind a layer needs a layer rule, so even a desktop with blur on
globally does not blur behind omapad now - and that is the point: nothing
about the picture behind the menu is omapad's to decide.

**Rejected:** shipping `[ui] blur` off and keeping the rule behind it for
whoever turned it on. That was the first pass. It still left omapad with a
look of its own to maintain against the desktop, and a watcher on Hyprland's
config that existed for nothing else.

**Also rejected:** having the daemon turn `decoration.blur.enabled` on. It is
every window's setting, not the panel's, and it would reverse a choice
Omarchy made on purpose.
