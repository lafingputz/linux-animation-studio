"""v0.32 timeline thumbnail performance: cold, warm, and one-frame edit.

Compare on the same computer in the LAS venv. This is a microbenchmark,
not a promise about real brush latency or playback FPS.
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import statistics
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QPainter
from main import Canvas, Layer, transparent_image
import uuid


def time_pass(canvas):
    start = time.perf_counter()
    for frame in range(len(canvas.frames)):
        canvas.frame_thumbnail(frame)
    return (time.perf_counter() - start) * 1000


def main():
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    canvas.reset_document(1200, 800)
    # Keep the app alive until the benchmark completes.
    canvas.frames = [[Layer(uuid.uuid4().hex, 'Cel', transparent_image(1200, 800))]
                     for _ in range(120)]
    cold = time_pass(canvas)
    warm = [time_pass(canvas) for _ in range(5)]
    # Touch the raster of a single frame; the remaining thumbnails stay valid.
    p = QPainter(canvas.frames[60][0].image)
    p.fillRect(0, 0, 50, 50, QColor('#cc3344'))
    p.end()
    edited = time_pass(canvas)
    print(f'120 frames @ 1200x800: cold={cold:.2f} ms; warm median={statistics.median(warm):.2f} ms; after one cel edit={edited:.2f} ms')
    print('Cache:', canvas.thumbnail_cache_stats())
    print('Timing varies by system. Verify brush, undo/redo, holds, motion, and export behavior in the GUI.')


if __name__ == '__main__':
    main()
