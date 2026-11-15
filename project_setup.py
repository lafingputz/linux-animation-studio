"""Pure canvas-dimension math for Linux Animation Studio project creation."""
from math import isfinite

PROJECT_PRESETS = (
    ('default', 'LAS Default (1200 × 800)'),
    ('screen', 'Screen Size (current display)'),
    ('square', 'Square (2048 × 2048)'),
    ('4k', '4K Wide (4096 × 1714)'),
    ('a4', 'A4 Portrait (210 × 297 mm)'),
    ('photo', '4 × 6 Photo, landscape (6 × 4 in)'),
    ('letter', 'US Letter, landscape (11 × 8.5 in)'),
    ('1080', '1080p (1920 × 1080)'),
    ('uhd', 'UHD 4K (3840 × 2160)'),
    ('custom', 'Custom'),
)


def unit_to_pixels(value, unit, ppi):
    value = float(value)
    if not isfinite(value) or not isfinite(ppi) or ppi <= 0:
        raise ValueError('Invalid canvas measurement')
    if unit == 'px':
        return round(value)
    if unit == 'in':
        return round(value * ppi)
    if unit == 'mm':
        return round(value * ppi / 25.4)
    raise ValueError('Unknown measurement unit')


def pixels_to_unit(value, unit, ppi):
    if ppi <= 0:
        raise ValueError('PPI must be positive')
    if unit == 'px':
        return float(value)
    if unit == 'in':
        return float(value) / ppi
    if unit == 'mm':
        return float(value) * 25.4 / ppi
    raise ValueError('Unknown measurement unit')


def preset_dimensions(key, ppi=300):
    fixed = {
        'default': (1200, 800), 'square': (2048, 2048),
        '4k': (4096, 1714), '1080': (1920, 1080),
        'uhd': (3840, 2160),
    }
    if key in fixed:
        return fixed[key]
    physical = {'a4': (210, 297, 'mm'), 'photo': (6, 4, 'in'), 'letter': (11, 8.5, 'in')}
    if key in physical:
        w, h, unit = physical[key]
        return unit_to_pixels(w, unit, ppi), unit_to_pixels(h, unit, ppi)
    raise ValueError('Custom/screen presets require external dimensions')


def validate_project_dimensions(width, height, max_side=16384):
    if not 1 <= width <= max_side or not 1 <= height <= max_side:
        raise ValueError(f'Canvas dimensions must be between 1 and {max_side:,} pixels')
    return width, height


def resize_linked_dimension(changed_axis, entered_pixels, aspect_ratio, max_side=16384):
    """Resize one pixel dimension while preserving an existing width/height ratio.

    Returns (width, height), with both dimensions kept in the supported range.
    Pixel rounding may differ from the exact mathematical ratio by a fraction
    of a pixel, which is unavoidable for raster canvases.
    """
    if changed_axis not in ('width', 'height'):
        raise ValueError('Unknown dimension')
    if not isfinite(aspect_ratio) or aspect_ratio <= 0:
        raise ValueError('Invalid aspect ratio')
    if not isfinite(entered_pixels):
        raise ValueError('Invalid dimension')
    primary = max(1, min(max_side, round(entered_pixels)))
    if changed_axis == 'width':
        primary = min(primary, max(1, int(max_side * aspect_ratio)))
        return primary, max(1, min(max_side, round(primary / aspect_ratio)))
    primary = min(primary, max(1, int(max_side / aspect_ratio)))
    return max(1, min(max_side, round(primary * aspect_ratio))), primary
