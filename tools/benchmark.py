"""Reproducible baseline benchmark, not an optimizer or a performance guarantee."""
import os
import statistics
import time
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor
from main import Canvas

def main():
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    canvas.reset_document(1200, 800)
    times = []
    for i in range(25):
        start = time.perf_counter()
        image = canvas.composite(False)
        assert not image.isNull()
        times.append((time.perf_counter() - start)*1000)
    print(f'Composite baseline 1200x800 (25 runs): median {statistics.median(times):.2f}ms, p95 {sorted(times)[23]:.2f}ms')
    print('Compare the same machine/OS and workload across versions. Real pen/playback use still requires interactive testing.')

if __name__ == '__main__':
    main()
