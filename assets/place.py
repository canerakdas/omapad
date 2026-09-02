"""Where a label sits inside a button, decided by the shape rather than by eye.

A face button is symmetric and its letter goes in the middle, but a shoulder
is not: LB and RB are drawn with one corner rounded away, and a label centred
on the bounding box crowds the cut. The hand-drawn examples this folder
started from put the text where the shape is roomiest, so that is what is
computed here instead of a table of nudges per shape:

1. rasterise the filled shape to a mask,
2. take the distance from every point inside it to the nearest point outside,
3. slide the label's box over that field and keep, for each position, the
   smallest clearance the box sees,
4. put the label where that number is largest - the deepest the box can sit
   inside the shape - preferring the position nearest the shape's middle when
   several tie.

Shrink the label and re-run when it does not fit at all. Everything is on a
64x32 grid at a handful of samples per unit, so the whole pass is thousands of
cells and runs in milliseconds.
"""

import collections

import svgpath

# Samples per shape unit. Four puts the sub-unit clearances the placement
# compares (the examples differ by ~1 unit) safely above the grid's own noise;
# past that the mask costs more and decides nothing.
SAMPLES = 4


def rasterize(polys, width, height, samples=SAMPLES):
    """Even-odd scanline fill of the shape, as rows of booleans."""
    cols, rows = int(width * samples), int(height * samples)
    mask = [[False] * cols for _ in range(rows)]
    edges = []
    for poly in polys:
        for i in range(len(poly)):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % len(poly)]
            if y0 != y1:
                edges.append((x0 * samples, y0 * samples,
                              x1 * samples, y1 * samples))
    for row in range(rows):
        y = row + 0.5
        crossings = []
        for x0, y0, x1, y1 in edges:
            if (y0 <= y < y1) or (y1 <= y < y0):
                crossings.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
        crossings.sort()
        for i in range(0, len(crossings) - 1, 2):
            first = max(0, int(crossings[i] + 0.5))
            last = min(cols, int(crossings[i + 1] + 0.5))
            for col in range(first, last):
                mask[row][col] = True
    return mask


def _edt_1d(f):
    """Felzenszwalb's exact squared distance transform of one row."""
    n = len(f)
    out = [0.0] * n
    v = [0] * n
    z = [0.0] * (n + 1)
    k = 0
    v[0] = 0
    z[0] = -1e30
    z[1] = 1e30
    for q in range(1, n):
        while True:
            s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2.0 * q - 2.0 * v[k])
            if s <= z[k]:
                k -= 1
            else:
                break
        k += 1
        v[k] = q
        z[k] = s
        z[k + 1] = 1e30
    k = 0
    for q in range(n):
        while z[k + 1] < q:
            k += 1
        out[q] = (q - v[k]) ** 2 + f[v[k]]
    return out


def distance_field(mask):
    """Distance from each cell to the nearest cell outside the shape.

    Everything past the viewBox counts as outside, so a shape that runs to its
    own edge - all of these do - is measured against that edge as well. Done
    by clamping afterwards rather than by padding the grid, which would be the
    same answer for several times the work.
    """
    rows, cols = len(mask), len(mask[0])
    big = float(rows * rows + cols * cols) * 4
    grid = [[big if mask[r][c] else 0.0 for c in range(cols)]
            for r in range(rows)]
    for c in range(cols):
        column = _edt_1d([grid[r][c] for r in range(rows)])
        for r in range(rows):
            grid[r][c] = column[r]
    for r in range(rows):
        grid[r] = _edt_1d(grid[r])
    return [[min(grid[r][c] ** 0.5, r + 0.5, c + 0.5,
                 rows - r - 0.5, cols - c - 0.5) if mask[r][c] else 0.0
             for c in range(cols)]
            for r in range(rows)]


def _sliding_min(values, window):
    """Minimum over every `window`-wide run, centred, edges clamped shut."""
    n = len(values)
    if window <= 1:
        return list(values)
    half = window // 2
    out = [0.0] * n
    queue = collections.deque()
    for i in range(n + half):
        if i < n:
            while queue and values[queue[-1]] >= values[i]:
                queue.pop()
            queue.append(i)
        centre = i - half
        if centre >= 0:
            while queue[0] < centre - half:
                queue.popleft()
            # A window that runs off the end has nothing inside the shape
            # there, so the run is closed rather than clipped.
            out[centre] = 0.0 if (centre - half < 0 or centre + half >= n) \
                else values[queue[0]]
    return out


def clearance_field(field, box_w, box_h):
    """For each centre, the least clearance a `box_w` x `box_h` box sees."""
    rows, cols = len(field), len(field[0])
    grid = [_sliding_min(field[r], box_w) for r in range(rows)]
    for c in range(cols):
        column = _sliding_min([grid[r][c] for r in range(rows)], box_h)
        for r in range(rows):
            grid[r][c] = column[r]
    return grid


# How much clearance a placement may give up to sit nearer the middle of the
# shape, in shape units. Without it the label slides to whichever end of a
# strip is a hair deeper; with it, a shape that is equally comfortable across
# a stretch centres the label in that stretch, which is what the eye expects.
SETTLE = 0.75


def best_centre(mask, field, box_w, box_h, samples=SAMPLES, settle=SETTLE):
    """(x, y, clearance) for the roomiest placement of a box, in shape units.

    Near-ties go to the position nearest the shape's own centre of area: a
    bumper is a strip and its best row is most of the columns in it, so the
    deepest cell alone is not an answer anyone would have drawn.
    """
    grid = clearance_field(field, int(round(box_w * samples)),
                           int(round(box_h * samples)))
    total = sum(1 for row in mask for cell in row if cell)
    if not total:
        return None
    mid_x = sum(c for row in mask for c, cell in enumerate(row) if cell) / total
    mid_y = sum(r for r, row in enumerate(mask) for cell in row if cell) / total
    deepest = max(max(row) for row in grid)
    if deepest <= 0:
        return None
    floor = deepest - settle * samples
    best = None
    for r, row in enumerate(grid):
        for c, value in enumerate(row):
            if value < floor or value <= 0:
                continue
            pull = (c - mid_x) ** 2 + (r - mid_y) ** 2
            if best is None or pull < best[0]:
                best = (pull, c, r, value)
    _, c, r, value = best
    return ((c + 0.5) / samples, (r + 0.5) / samples, value / samples)


def shape_mask(paths, width, height, samples=SAMPLES):
    polys = []
    for data in paths:
        polys.extend(svgpath.flatten(data))
    return rasterize(polys, width, height, samples)
