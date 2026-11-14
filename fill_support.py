"""Efficient Qt-independent scanline flood fill for LAS raster cels.

Pixels are straight-ARGB 0xAARRGGBB integers. Return a binary region mask;
source pixels and selection input are never mutated.
"""


def flood_region(pixels, width, height, x, y, tolerance=0, contiguous=True, allowed=None):
    """Find pixels matching the seed within tolerance in all RGBA channels.

    A fully transparent pixel matches any other fully transparent pixel,
    independently of its otherwise invisible RGB components.
    """
    width, height = int(width), int(height)
    count = width * height
    if width <= 0 or height <= 0 or len(pixels) != count:
        raise ValueError('Invalid image size or pixel buffer')
    if allowed is not None and len(allowed) != count:
        raise ValueError('Invalid selection mask')
    result = bytearray(count)
    if not (0 <= x < width and 0 <= y < height):
        return result
    start = y * width + x
    if allowed is not None and not allowed[start]:
        return result
    tolerance = max(0, min(255, int(tolerance)))
    seed = int(pixels[start])
    seed_a = (seed >> 24) & 255
    seed_r = (seed >> 16) & 255 if seed_a else 0
    seed_g = (seed >> 8) & 255 if seed_a else 0
    seed_b = seed & 255 if seed_a else 0

    # Avoid allocating 4-tuples and running all()/zip() for every visited pixel.
    def matches(index):
        if allowed is not None and not allowed[index]:
            return False
        value = int(pixels[index])
        alpha = (value >> 24) & 255
        if alpha == 0:
            return (abs(seed_a) <= tolerance and seed_r <= tolerance
                    and seed_g <= tolerance and seed_b <= tolerance)
        return (abs(alpha - seed_a) <= tolerance
                and abs(((value >> 16) & 255) - seed_r) <= tolerance
                and abs(((value >> 8) & 255) - seed_g) <= tolerance
                and abs((value & 255) - seed_b) <= tolerance)

    if not contiguous:
        for i in range(count):
            if matches(i):
                result[i] = 1
        return result

    # Visit each matching horizontal run once. Only queue the beginning of
    # a vertical neighbor's matching run, not every pixel above/below the run.
    pending = [start]
    while pending:
        seed_index = pending.pop()
        if result[seed_index] or not matches(seed_index):
            continue
        row_start = seed_index // width * width
        row_end = row_start + width
        left = seed_index
        while left > row_start and not result[left - 1] and matches(left - 1):
            left -= 1
        right = seed_index
        while right + 1 < row_end and not result[right + 1] and matches(right + 1):
            right += 1
        result[left:right + 1] = b'\x01' * (right - left + 1)

        for neighbor_offset in (-width, width):
            if not 0 <= left + neighbor_offset < count:
                continue
            in_run = False
            for i in range(left + neighbor_offset, right + neighbor_offset + 1):
                eligible = not result[i] and matches(i)
                if eligible and not in_run:
                    pending.append(i)
                in_run = eligible
    return result


def expand_region(region, width, height, radius, allowed=None):
    """Expand a binary fill mask by up to ``radius`` pixels (square footprint).

    This operates on the *resulting region*, never the boundary tolerance.
    Selection restrictions are reapplied after expansion, so the fringe cannot
    escape a selection even if selected pixels surround unselected holes.
    Runs in O(width * height) for any radius using horizontal + vertical passes.
    The input is not mutated.
    """
    width, height = int(width), int(height)
    n = width * height
    if width <= 0 or height <= 0 or len(region) != n:
        raise ValueError('Invalid region dimensions')
    if allowed is not None and len(allowed) != n:
        raise ValueError('Invalid selection mask')
    radius = max(0, min(10, int(radius)))
    original = bytearray(bool(v) for v in region)
    if radius == 0 or not any(original):
        if allowed is not None:
            for i, selected in enumerate(allowed):
                if not selected:
                    original[i] = 0
        return original
    horizontal = bytearray(n)
    # Centered sliding window, reset at each row (never wrap horizontally).
    for y in range(height):
        start = y * width
        running = sum(original[start:start + min(width, radius + 1)])
        for x in range(width):
            horizontal[start + x] = int(running > 0)
            add_x = x + radius + 1
            remove_x = x - radius
            if add_x < width:
                running += original[start + add_x]
            if remove_x >= 0:
                running -= original[start + remove_x]
    expanded = bytearray(n)
    for x in range(width):
        running = sum(horizontal[x + y * width] for y in range(min(height, radius + 1)))
        for y in range(height):
            i = y * width + x
            expanded[i] = int(running > 0 and (allowed is None or allowed[i]))
            add_y = y + radius + 1
            remove_y = y - radius
            if add_y < height:
                running += horizontal[add_y * width + x]
            if remove_y >= 0:
                running -= horizontal[remove_y * width + x]
    return expanded
