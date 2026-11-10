"""Reproducible flood-region benchmarks; runs without PySide6.

Measures search-mask generation only, not Qt compositing or GUI refresh.
Compare the same machine and canvas size across releases.
"""
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fill_support import flood_region


def main():
    width, height = 1200, 800
    pixels = [0] * (width * height)
    for contiguous in (True, False):
        timings = []
        for _ in range(3):
            started = time.perf_counter()
            mask = flood_region(pixels, width, height, width // 2, height // 2, 24, contiguous)
            timings.append(1000 * (time.perf_counter() - started))
            assert sum(mask) == width * height
        print(f'Full transparent 1200x800 / {"contiguous" if contiguous else "global"}: '
              f'median={statistics.median(timings):.2f} ms; '
              f'runs={", ".join(f"{t:.2f}" for t in timings)} ms')
    print('Pure region search only; actual fills include Qt QImage conversions, overlays, and history.')


if __name__ == '__main__':
    main()
