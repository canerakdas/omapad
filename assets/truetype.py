"""Just enough TrueType to turn a string into SVG path data.

There is no font library in the standard library and this project takes no
third-party dependencies, so the tables the job actually needs are read here:
`head` for the em square, `cmap` for character to glyph, `loca`/`glyf` for the
outlines, `hmtx` for how far the pen moves and `OS/2` for the cap height the
labels are centred on.

Outlines only - no hinting, no ligatures, no kerning. The labels are two or
three capitals and digits from a monospaced face, which is the one case where
that is not a simplification but the whole truth.
"""

import struct


class Font(object):
    def __init__(self, path):
        with open(path, "rb") as handle:
            self.data = handle.read()
        self.tables = self._directory()
        head = self.tables["head"]
        self.units_per_em = struct.unpack_from(">H", self.data, head + 18)[0]
        self.loc_format = struct.unpack_from(">h", self.data, head + 50)[0]
        self.num_glyphs = struct.unpack_from(
            ">H", self.data, self.tables["maxp"] + 4)[0]
        self.cmap = self._cmap()
        self.advances = self._advances()
        self.cap_height = self._cap_height()

    def _directory(self):
        count = struct.unpack_from(">H", self.data, 4)[0]
        tables = {}
        for i in range(count):
            off = 12 + i * 16
            tag = self.data[off:off + 4].decode("ascii")
            tables[tag] = struct.unpack_from(">I", self.data, off + 8)[0]
        for tag in ("head", "maxp", "cmap", "loca", "glyf", "hhea", "hmtx"):
            if tag not in tables:
                raise ValueError("font has no %s table" % tag)
        return tables

    def _cmap(self):
        base = self.tables["cmap"]
        count = struct.unpack_from(">H", self.data, base + 2)[0]
        best = None
        for i in range(count):
            plat, enc, off = struct.unpack_from(">HHI", self.data,
                                                base + 4 + i * 8)
            # Windows BMP or full repertoire, in that order of preference:
            # every label here is ASCII, so the BMP table is always enough.
            rank = {(3, 10): 2, (3, 1): 1, (0, 4): 2, (0, 3): 1}.get(
                (plat, enc), 0)
            if rank and (best is None or rank > best[0]):
                best = (rank, base + off)
        if best is None:
            raise ValueError("font has no usable cmap subtable")
        return self._cmap_subtable(best[1])

    def _cmap_subtable(self, off):
        fmt = struct.unpack_from(">H", self.data, off)[0]
        table = {}
        if fmt == 4:
            seg2 = struct.unpack_from(">H", self.data, off + 6)[0]
            segs = seg2 // 2
            ends = off + 14
            starts = ends + seg2 + 2
            deltas = starts + seg2
            ranges = deltas + seg2
            for i in range(segs):
                end = struct.unpack_from(">H", self.data, ends + i * 2)[0]
                start = struct.unpack_from(">H", self.data, starts + i * 2)[0]
                delta = struct.unpack_from(">h", self.data, deltas + i * 2)[0]
                offset = struct.unpack_from(">H", self.data, ranges + i * 2)[0]
                if start == 0xFFFF:
                    continue
                for code in range(start, end + 1):
                    if offset == 0:
                        glyph = (code + delta) & 0xFFFF
                    else:
                        at = ranges + i * 2 + offset + (code - start) * 2
                        glyph = struct.unpack_from(">H", self.data, at)[0]
                        if glyph:
                            glyph = (glyph + delta) & 0xFFFF
                    if glyph:
                        table[code] = glyph
        elif fmt == 12:
            groups = struct.unpack_from(">I", self.data, off + 12)[0]
            for i in range(groups):
                start, end, glyph = struct.unpack_from(
                    ">III", self.data, off + 16 + i * 12)
                for code in range(start, end + 1):
                    table[code] = glyph + (code - start)
        else:
            raise ValueError("unsupported cmap format %d" % fmt)
        return table

    def _advances(self):
        count = struct.unpack_from(">H", self.data, self.tables["hhea"] + 34)[0]
        base = self.tables["hmtx"]
        widths = [struct.unpack_from(">H", self.data, base + i * 4)[0]
                  for i in range(count)]
        if not widths:
            raise ValueError("font has no horizontal metrics")
        # Past numberOfHMetrics every glyph keeps the last advance.
        return widths + [widths[-1]] * (self.num_glyphs - count)

    def _cap_height(self):
        """Where the capitals stop, which is what a badge is centred on.

        OS/2 version 2 added it; older fonts get the height of `H` measured
        off its own outline, which is the same number by definition.
        """
        os2 = self.tables.get("OS/2")
        if os2 is not None:
            version = struct.unpack_from(">H", self.data, os2)[0]
            if version >= 2:
                value = struct.unpack_from(">h", self.data, os2 + 88)[0]
                if value > 0:
                    return value
        glyph = self.cmap.get(ord("H"))
        if glyph is None:
            return int(self.units_per_em * 0.7)
        top = max((y for contour in self.contours(glyph) for _, y, _ in contour),
                  default=0)
        return top or int(self.units_per_em * 0.7)

    def _glyph_range(self, glyph):
        base = self.tables["loca"]
        if self.loc_format == 0:
            start, end = struct.unpack_from(">HH", self.data, base + glyph * 2)
            start, end = start * 2, end * 2
        else:
            start, end = struct.unpack_from(">II", self.data, base + glyph * 4)
        return self.tables["glyf"] + start, self.tables["glyf"] + end

    def contours(self, glyph, depth=0):
        """Contours as [(x, y, on_curve)], in font units, y up."""
        start, end = self._glyph_range(glyph)
        if end <= start:
            return []
        count = struct.unpack_from(">h", self.data, start)[0]
        if count < 0:
            return self._composite(start + 10, depth)
        off = start + 10
        ends = [struct.unpack_from(">H", self.data, off + i * 2)[0]
                for i in range(count)]
        off += count * 2
        instructions = struct.unpack_from(">H", self.data, off)[0]
        off += 2 + instructions
        total = ends[-1] + 1 if ends else 0

        flags = []
        while len(flags) < total:
            flag = self.data[off]
            off += 1
            flags.append(flag)
            if flag & 0x08:
                repeat = self.data[off]
                off += 1
                flags.extend([flag] * repeat)

        def coords(short_bit, same_bit):
            values = []
            value = 0
            pos = off
            for flag in flags:
                if flag & short_bit:
                    delta = self.data[pos]
                    pos += 1
                    value += delta if flag & same_bit else -delta
                elif not flag & same_bit:
                    value += struct.unpack_from(">h", self.data, pos)[0]
                    pos += 2
                values.append(value)
            return values, pos

        xs, off = coords(0x02, 0x10)
        ys, _ = coords(0x04, 0x20)

        out = []
        first = 0
        for last in ends:
            out.append([(xs[i], ys[i], bool(flags[i] & 0x01))
                        for i in range(first, last + 1)])
            first = last + 1
        return out

    def _composite(self, off, depth):
        if depth > 5:
            raise ValueError("composite glyph nested too deep")
        out = []
        while True:
            flags, index = struct.unpack_from(">HH", self.data, off)
            off += 4
            if flags & 0x0001:
                a, b = struct.unpack_from(">hh", self.data, off)
                off += 4
            else:
                a, b = struct.unpack_from(">bb", self.data, off)
                off += 2
            xx = yy = 1.0
            xy = yx = 0.0
            if flags & 0x0008:
                xx = yy = _f2dot14(self.data, off)
                off += 2
            elif flags & 0x0040:
                xx = _f2dot14(self.data, off)
                yy = _f2dot14(self.data, off + 2)
                off += 4
            elif flags & 0x0080:
                xx = _f2dot14(self.data, off)
                yx = _f2dot14(self.data, off + 2)
                xy = _f2dot14(self.data, off + 4)
                yy = _f2dot14(self.data, off + 6)
                off += 8
            dx, dy = (a, b) if flags & 0x0002 else (0, 0)
            for contour in self.contours(index, depth + 1):
                out.append([(x * xx + y * xy + dx, x * yx + y * yy + dy, on)
                            for x, y, on in contour])
            if not flags & 0x0020:
                break
        return out

    def advance(self, char):
        return self.advances[self.cmap.get(ord(char), 0)]

    def glyph_path(self, char, scale, origin_x, baseline_y, decimals=3):
        """One character as SVG path data, y down, at `scale` per font unit."""
        glyph = self.cmap.get(ord(char))
        if glyph is None:
            raise ValueError("font has no glyph for %r" % char)
        parts = []
        for contour in self.contours(glyph):
            parts.append(_contour_path(contour, scale, origin_x, baseline_y,
                                       decimals))
        return "".join(p for p in parts if p)


def _f2dot14(data, off):
    return struct.unpack_from(">h", data, off)[0] / 16384.0


def _contour_path(contour, scale, origin_x, baseline_y, decimals):
    """One TrueType contour as quadratics.

    TrueType leaves the on-curve point between two consecutive off-curve
    points implied, at their midpoint, and a contour may start off-curve; both
    are put back here so the result is a plain run of `Q` segments.
    """
    if not contour:
        return ""

    def point(p):
        return (origin_x + p[0] * scale, baseline_y - p[1] * scale)

    def num(v):
        text = "%.*f" % (decimals, v)
        text = text.rstrip("0").rstrip(".") if "." in text else text
        return text or "0"

    points = list(contour)
    if not points[0][2]:
        # Start on a real point: the last on-curve one, or the implied
        # midpoint when the whole contour is off-curve.
        on = next((i for i, p in enumerate(points) if p[2]), None)
        if on is None:
            first, last = points[0], points[-1]
            mid = ((first[0] + last[0]) / 2.0, (first[1] + last[1]) / 2.0, True)
            points.insert(0, mid)
        else:
            points = points[on:] + points[:on]

    start = point(points[0])
    out = ["M%s %s" % (num(start[0]), num(start[1]))]
    i = 1
    pending = None
    while i <= len(points):
        p = points[i % len(points)]
        if p[2]:
            here = point(p)
            if pending is None:
                out.append("L%s %s" % (num(here[0]), num(here[1])))
            else:
                out.append("Q%s %s %s %s" % (num(pending[0]), num(pending[1]),
                                             num(here[0]), num(here[1])))
                pending = None
        else:
            here = point(p)
            if pending is not None:
                mid = ((pending[0] + here[0]) / 2.0,
                       (pending[1] + here[1]) / 2.0)
                out.append("Q%s %s %s %s" % (num(pending[0]), num(pending[1]),
                                             num(mid[0]), num(mid[1])))
            pending = here
        i += 1
    out.append("Z")
    return "".join(out)
