# 73. The sentence that had nowhere to go · ✅ Done · S

Asked for from the sofa, right after push to talk landed: *oyun menusunun
altina yeni bir kart ekle toggle olsun, push to talk'i clipboard'a otomatik
kopyalasin aktifken.* Dictation types at the cursor, which is the right answer
while there is a text field under it and the wrong one the rest of the time -
a game, a terminal running something, a window that is not yours at all takes
the sentence and loses it.

`Audio > Dictate to clipboard` is the switch, on the page with the outputs and
the microphones because it is the same question asked of the other end of the
microphone rather than a thing about the pad.

**What it cost is a boundary being named.** omapad never sees the words:
voxtype types them itself and leaves no transcript anywhere, so there is
nothing here to redirect and the only thing there is to switch is voxtype's
own `[output] mode`. So `dictate_clipboard` is the first `pad:` setting that
holds no behaviour of its own - `apply_setting` spawns a command and that is
the whole of it - and the commands are shipped as a **default rather than a
mechanism**: they fit the voxtype Omarchy installs, and a machine that keeps
that setting elsewhere replaces the pair. One half of it without the other is
refused at load, because a switch that can only go one way leaves the words on
the clipboard for good with nothing on the pad saying why.
