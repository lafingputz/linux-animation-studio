import sys
from pathlib import Path
from PySide6.QtCore import Qt, QEvent, QPointF, Signal, QRectF
from PySide6.QtGui import QAction, QColor, QImage, QPainter, QPen, QBrush
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QSlider, QLabel, QColorDialog, QFileDialog, QScrollArea)

class Canvas(QWidget):
    diagnostic = Signal(str)
    def __init__(self):
        super().__init__()
        self.image = QImage(1200, 800, QImage.Format.Format_ARGB32_Premultiplied)
        self.image.fill(Qt.GlobalColor.white)
        self.setFixedSize(self.image.size())
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)
        self.color = QColor('#222222')
        self.size = 12
        self.eraser = False
        self.drawing = False
        self.last = None
        self.last_pressure = 1.0
        self.last_tablet = False
        self.ignore_mouse = False
        self.hover_position = None
        self.hover_pressure = 1.0
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.BlankCursor)

    def cursor_rect(self, pos=None):
        pos = self.hover_position if pos is None else pos
        if pos is None:
            return QRectF()
        diameter = self.size if self.eraser else self.size * (0.15 + 0.85 * self.hover_pressure)
        radius = max(3.0, diameter / 2.0)
        return QRectF(pos.x() - radius - 4, pos.y() - radius - 4,
                      2 * radius + 8, 2 * radius + 8)

    def show_hover(self, pos, pressure=None):
        old = self.cursor_rect()
        self.hover_position = QPointF(pos)
        if pressure is not None:
            self.hover_pressure = max(0.0, min(1.0, pressure))
        self.update(old.toAlignedRect())
        self.update(self.cursor_rect().toAlignedRect())

    def refresh_cursor(self):
        self.update(self.cursor_rect().toAlignedRect())

    def leaveEvent(self, event):
        old = self.cursor_rect()
        self.hover_position = None
        self.update(old.toAlignedRect())
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawImage(0, 0, self.image)
        if self.hover_position is not None:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            diameter = self.size if self.eraser else self.size * (0.15 + 0.85 * self.hover_pressure)
            center = self.hover_position
            if self.eraser:
                # Thin contrasting rings show the exact eraser footprint.
                radius = diameter / 2.0
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
                painter.drawEllipse(center, radius, radius)
                painter.setPen(QPen(QColor(35, 35, 35, 235), 1))
                painter.drawEllipse(center, radius, radius)
            else:
                # Tiny two-tone center dot, independent of brush diameter.
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 235))
                painter.drawEllipse(center, 2.5, 2.5)
                painter.setBrush(QColor(25, 25, 25, 235))
                painter.drawEllipse(center, 1.3, 1.3)

    def stroke(self, point, pressure, tablet):
        pressure = max(0.0, min(1.0, pressure))
        # Don't allow a real pressed pen to completely disappear at near-zero force.
        width = self.size * (0.15 + 0.85 * pressure) if tablet else self.size
        color = QColor(Qt.GlobalColor.white) if self.eraser else self.color
        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if self.last is None:
            painter.drawPoint(point)
        else:
            painter.drawLine(self.last, point)
        painter.end()
        self.last = point
        self.last_pressure = pressure
        self.update()

    def tabletEvent(self, event):
        typ = event.type()
        pressure = float(event.pressure())
        self.show_hover(event.position(), pressure if self.drawing else 1.0)
        device = event.pointingDevice()
        device_name = device.name() if device else 'Unknown tablet'
        if typ == QEvent.Type.TabletPress:
            self.drawing = True
            self.last = None
            self.ignore_mouse = True
            self.stroke(event.position(), pressure, True)
        elif typ == QEvent.Type.TabletMove:
            if self.drawing:
                self.stroke(event.position(), pressure, True)
        elif typ == QEvent.Type.TabletRelease:
            if self.drawing:
                self.stroke(event.position(), pressure, True)
            self.drawing = False
            self.last = None
            self.ignore_mouse = False
        self.diagnostic.emit(f'TABLET: {device_name}  |  pressure: {pressure:.3f}  |  tilt: {event.xTilt():.0f}, {event.yTilt():.0f}  |  {typ.name}')
        event.accept()

    def mousePressEvent(self, event):
        self.show_hover(event.position(), 1.0)
        if not self.ignore_mouse and event.button() == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.last = None
            self.stroke(event.position(), 1.0, False)
            self.diagnostic.emit('MOUSE input (fixed width; no pressure)')
        event.accept()

    def mouseMoveEvent(self, event):
        if not self.ignore_mouse:
            self.show_hover(event.position(), 1.0)
        if not self.ignore_mouse and self.drawing and event.buttons() & Qt.MouseButton.LeftButton:
            self.stroke(event.position(), 1.0, False)
        event.accept()

    def mouseReleaseEvent(self, event):
        if not self.ignore_mouse and event.button() == Qt.MouseButton.LeftButton:
            self.drawing = False
            self.last = None
        event.accept()

    def clear(self):
        self.image.fill(Qt.GlobalColor.white)
        self.update()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Linux Animation Studio - Tablet Prototype 0.2')
        self.resize(1100, 850)
        center = QWidget()
        layout = QVBoxLayout(center)
        bar = QHBoxLayout()
        self.canvas = Canvas()
        self.status = QLabel('Draw with Wacom stylus to see pressure values here.')
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.canvas.diagnostic.connect(self.status.setText)

        color_button = QPushButton('Brush color')
        color_button.clicked.connect(self.pick_color)
        bar.addWidget(color_button)
        self.erase_button = QPushButton('Eraser: OFF')
        self.erase_button.setCheckable(True)
        self.erase_button.toggled.connect(self.toggle_eraser)
        bar.addWidget(self.erase_button)
        bar.addWidget(QLabel('Size:'))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(1, 80)
        slider.setValue(self.canvas.size)
        slider.setMaximumWidth(140)
        slider.valueChanged.connect(self.change_size)
        bar.addWidget(slider)
        clear_button = QPushButton('Clear')
        clear_button.clicked.connect(self.canvas.clear)
        bar.addWidget(clear_button)
        export_button = QPushButton('Export PNG')
        export_button.clicked.connect(self.export_png)
        bar.addWidget(export_button)
        bar.addStretch()
        layout.addLayout(bar)
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(scroll)
        layout.addWidget(self.status)
        self.setCentralWidget(center)

    def change_size(self, size):
        old = self.canvas.cursor_rect()
        self.canvas.size = size
        self.canvas.update(old.toAlignedRect())
        self.canvas.refresh_cursor()

    def toggle_eraser(self, checked):
        self.canvas.eraser = checked
        self.erase_button.setText('Eraser: ON' if checked else 'Eraser: OFF')
        self.canvas.refresh_cursor()

    def pick_color(self):
        color = QColorDialog.getColor(self.canvas.color, self, 'Choose brush color')
        if color.isValid():
            self.canvas.color = color
            self.erase_button.setChecked(False)

    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export image',
                str(Path.home() / 'drawing.png'), 'PNG files (*.png)')
        if path:
            ok = self.canvas.image.save(path, 'PNG')
            self.status.setText(('Saved: ' if ok else 'Could not save: ') + path)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
