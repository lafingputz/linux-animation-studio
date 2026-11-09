"""Qt-independent, iterative flood fill for LAS raster cels.

Pixels are 0xAARRGGBB integers. The output is a one-byte-per-pixel mask;
no user artwork is modified by this module.
"""
from collections import deque


def flood_region(pixels, width, height, x, y, tolerance=0, contiguous=True, allowed=None):
    """Return a byte mask of pixels matching the clicked color.

    Tolerance is maximum absolute difference per straight RGBA channel (0..255).
    Fully transparent pixels compare as transparent regardless of stored RGB.
    If provided, allowed is a byte sequence of 0/1 values for selection bounds.
    """
    width, height = int(width), int(height)
    if width <= 0 or height <= 0 or len(pixels) != width * height:
        raise ValueError('Invalid image size or pixel buffer')
    if allowed is not None and len(allowed) != width * height:
        raise ValueError('Invalid selection mask')
    result = bytearray(width * height)
    if not (0 <= x < width and 0 <= y < height):
        return result
    initial = y * width + x
    if allowed is not None and not allowed[initial]:
        return result
    tolerance = max(0, min(255, int(tolerance)))
    seed = int(pixels[initial])
    def components(value):
        alpha = value >> 24 & 255
        if alpha == 0:
            return (0, 0, 0, 0)
        return (value >> 16 & 255, value >> 8 & 255, value & 255, alpha)
    target = components(seed)
    def matching(index):
        if allowed is not None and not allowed[index]:
            return False
        candidate = components(int(pixels[index]))
        return all(abs(a-b) <= tolerance for a,b in zip(candidate, target))
    if not contiguous:
        for i in range(width * height):
            if matching(i):
                result[i] = 1
        return result
    pending = deque([initial])
    # Scanline fill: mark each horizontal run once, enqueue vertical neighbors.
    while pending:
        pos = pending.pop()
        if result[pos] or not matching(pos):
            continue
        row_start = pos // width * width
        left, right = pos, pos
        while left > row_start and not result[left - 1] and matching(left - 1):
            left -= 1
        row_end = row_start + width
        while right + 1 < row_end and not result[right + 1] and matching(right + 1):
            right += 1
        for i in range(left, right + 1):
            result[i] = 1
            if i >= width and not result[i-width] and matching(i-width):
                pending.append(i-width)
            if i + width < width*height and not result[i+width] and matching(i+width):
                pending.append(i+width)
    return result
