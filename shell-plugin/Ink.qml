// Which of the theme's inks reads on a given ground.
//
// `Color.menu.selectedText` looks like the answer for anything filled with the
// accent, and it is not: Omarchy defaults that key to the **accent itself**.
// A tile filled solid with `Color.accent` and labelled with `selectedText`
// would be accent on accent - a label that is simply not there - on every
// theme that has not overridden it, which is nearly all of them.
//
// Every other state on these surfaces sidesteps the question by tinting
// rather than filling: a selection at a fifth of the accent still has the
// theme's own text colour standing on it. A solid fill is the one place that
// dodge runs out, and the bar of nav cards is where it happens.
//
// So it is measured rather than named. Relative luminance, the WCAG
// definition of it, and whichever candidate stands furthest from the ground
// wins. **Two candidates, never a third**: `menu.background` and `menu.text`
// are the two colours every theme is guaranteed to have defined, and a
// surface that invented a colour to put between them would be a console's own
// palette arriving through the back door - the thing `qml.md` 8.1 exists to
// stop. `selectedText` is not among them on purpose: its job is the ink on a
// *tinted* tile, and a theme that tuned it for that has said nothing about
// what reads on a solid one.
import QtQuick

QtObject {
  id: ink

  // sRGB channel, linearised. The standard's transfer function rather than an
  // approximation of it: the cheap `.299r + .587g + .114b` is a luma of
  // gamma-encoded values, and it calls a saturated mid-blue lighter than the
  // eye does - which on a blue accent is exactly the theme this has to get
  // right.
  function linear(c) {
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
  }

  function luminance(colour) {
    return 0.2126 * ink.linear(colour.r)
      + 0.7152 * ink.linear(colour.g)
      + 0.0722 * ink.linear(colour.b)
  }

  // The contrast ratio between two colours, 1 (identical) to 21 (black on
  // white). Alpha is not in it and cannot be: what a translucent colour comes
  // out as depends on everything behind it, and a caller that hands this one
  // is asking a question with no answer.
  function ratio(one, other) {
    var a = ink.luminance(one)
    var b = ink.luminance(other)
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
  }

  // The one of `first` and `second` that reads on `ground`. Ties go to
  // `first`, so a caller states its preference by the order it asks in.
  function on(ground, first, second) {
    return ink.ratio(ground, first) >= ink.ratio(ground, second)
      ? first : second
  }
}
