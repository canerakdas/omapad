"""SVG path data: parse it, flatten it, measure it.

Only what this folder's shapes are drawn with - Figma writes `M C H V L Z` and
an `A` for a circle, absolute and relative - plus enough of the rest that a
shape redrawn in another editor still loads. Flattening is to polygons because
the placement pass rasterises the shape; nothing here has to round-trip.
"""

import math
import re

NUMBER = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
COMMAND = re.compile(r"[MmZzLlHhVvCcSsQqTtAa]")

# Segments per curve when flattening. The shapes are 64 units across at most
# and the mask is sampled a few times per unit, so this is far finer than the
# grid it lands on - an implementation detail, not a knob.
CURVE_STEPS = 24


def tokenize(data):
    """(command, [numbers]) pairs, in order."""
    out = []
    pos = 0
    while pos < len(data):
        match = COMMAND.search(data, pos)
        if match is None:
            break
        command = match.group()
        end = COMMAND.search(data, match.end())
        chunk = data[match.end():end.start() if end else len(data)]
        out.append((command, [float(n) for n in NUMBER.findall(chunk)]))
        pos = match.end()
    return out


def _take(args, size):
    """Walk an argument list in groups, the way a repeated command reads."""
    for i in range(0, len(args) - size + 1, size):
        yield args[i:i + size]


def _bezier3(p0, p1, p2, p3, steps):
    for i in range(1, steps + 1):
        t = float(i) / steps
        u = 1.0 - t
        yield (u * u * u * p0[0] + 3 * u * u * t * p1[0]
               + 3 * u * t * t * p2[0] + t * t * t * p3[0],
               u * u * u * p0[1] + 3 * u * u * t * p1[1]
               + 3 * u * t * t * p2[1] + t * t * t * p3[1])


def _bezier2(p0, p1, p2, steps):
    for i in range(1, steps + 1):
        t = float(i) / steps
        u = 1.0 - t
        yield (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
               u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])


def _arc(p0, rx, ry, phi, large, sweep, p1, steps):
    """Endpoint-parameterised arc, per the SVG implementation notes."""
    if rx == 0 or ry == 0 or p0 == p1:
        yield p1
        return
    rx, ry = abs(rx), abs(ry)
    phi = math.radians(phi % 360.0)
    cos, sin = math.cos(phi), math.sin(phi)
    dx2, dy2 = (p0[0] - p1[0]) / 2.0, (p0[1] - p1[1]) / 2.0
    x1 = cos * dx2 + sin * dy2
    y1 = -sin * dx2 + cos * dy2
    # An out-of-range radius is scaled up until the arc exists at all.
    lam = (x1 * x1) / (rx * rx) + (y1 * y1) / (ry * ry)
    if lam > 1:
        rx *= math.sqrt(lam)
        ry *= math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    factor = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        factor = -factor
    cx1 = factor * rx * y1 / ry
    cy1 = -factor * ry * x1 / rx
    cx = cos * cx1 - sin * cy1 + (p0[0] + p1[0]) / 2.0
    cy = sin * cx1 + cos * cy1 + (p0[1] + p1[1]) / 2.0

    def angle(ux, uy):
        return math.atan2(uy, ux)

    start = angle((x1 - cx1) / rx, (y1 - cy1) / ry)
    end = angle((-x1 - cx1) / rx, (-y1 - cy1) / ry)
    sweep_angle = end - start
    if not sweep and sweep_angle > 0:
        sweep_angle -= 2 * math.pi
    elif sweep and sweep_angle < 0:
        sweep_angle += 2 * math.pi
    for i in range(1, steps + 1):
        theta = start + sweep_angle * i / steps
        ex, ey = rx * math.cos(theta), ry * math.sin(theta)
        yield (cos * ex - sin * ey + cx, sin * ex + cos * ey + cy)


def flatten(data, steps=CURVE_STEPS):
    """Path data as a list of closed polygons, in the path's own units."""
    polys = []
    poly = []
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    prev_cubic = None
    prev_quad = None

    def close():
        if len(poly) > 2:
            polys.append(list(poly))
        del poly[:]

    for command, args in tokenize(data):
        rel = command.islower()
        up = command.upper()
        if up == "M":
            for i, pair in enumerate(_take(args, 2)):
                point = ((cur[0] + pair[0], cur[1] + pair[1]) if rel
                         else (pair[0], pair[1]))
                if i == 0:
                    close()
                    start = point
                    poly.append(point)
                else:
                    poly.append(point)
                cur = point
            prev_cubic = prev_quad = None
        elif up == "Z":
            close()
            cur = start
            prev_cubic = prev_quad = None
        elif up in ("L", "H", "V"):
            size = {"L": 2, "H": 1, "V": 1}[up]
            for pair in _take(args, size):
                if up == "L":
                    point = ((cur[0] + pair[0], cur[1] + pair[1]) if rel
                             else (pair[0], pair[1]))
                elif up == "H":
                    point = (cur[0] + pair[0] if rel else pair[0], cur[1])
                else:
                    point = (cur[0], cur[1] + pair[0] if rel else pair[0])
                poly.append(point)
                cur = point
            prev_cubic = prev_quad = None
        elif up in ("C", "S"):
            size = 6 if up == "C" else 4
            for pair in _take(args, size):
                def at(i):
                    return ((cur[0] + pair[i], cur[1] + pair[i + 1]) if rel
                            else (pair[i], pair[i + 1]))
                if up == "C":
                    c1, c2, end = at(0), at(2), at(4)
                else:
                    c1 = (2 * cur[0] - prev_cubic[0], 2 * cur[1] - prev_cubic[1]) \
                        if prev_cubic else cur
                    c2, end = at(0), at(2)
                poly.extend(_bezier3(cur, c1, c2, end, steps))
                cur, prev_cubic, prev_quad = end, c2, None
        elif up in ("Q", "T"):
            size = 4 if up == "Q" else 2
            for pair in _take(args, size):
                def at(i):
                    return ((cur[0] + pair[i], cur[1] + pair[i + 1]) if rel
                            else (pair[i], pair[i + 1]))
                if up == "Q":
                    ctrl, end = at(0), at(2)
                else:
                    ctrl = (2 * cur[0] - prev_quad[0], 2 * cur[1] - prev_quad[1]) \
                        if prev_quad else cur
                    end = at(0)
                poly.extend(_bezier2(cur, ctrl, end, steps))
                cur, prev_quad, prev_cubic = end, ctrl, None
        elif up == "A":
            for pair in _take(args, 7):
                end = ((cur[0] + pair[5], cur[1] + pair[6]) if rel
                       else (pair[5], pair[6]))
                poly.extend(_arc(cur, pair[0], pair[1], pair[2],
                                 int(pair[3]), int(pair[4]), end, steps))
                cur = end
            prev_cubic = prev_quad = None
        else:
            raise ValueError("unsupported path command %r" % command)
    close()
    return polys


def circle_path(cx, cy, r):
    """A circle as path data, so it can be punched like any other shape."""
    return "M%g %gA%g %g 0 1 0 %g %gA%g %g 0 1 0 %g %gZ" % (
        cx - r, cy, r, r, cx + r, cy, r, r, cx - r, cy)
