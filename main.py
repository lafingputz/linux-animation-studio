"""Linux Animation Studio v0.3: pressure-sensitive drawing and bounded undo/redo."""
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QEvent, QPointF, QRect, QRectF, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QImage, QPainter, QPen, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLabel, QColorDialog, QFileDialog, QScrollArea,
)


class Canvas(QWidget):
    diagnostic = Signal(str)
    history_changed = Signal(bool, bool)
    MAX_UNDO_BYTES = 96 * 1024 * 1024
    MAX_UNDO_STEPS = 50

    def __init__(self):
        super().__init__()
        self.image = QImage(1200, 800, QImage.Format.Format_ARGB32_Premultiplied)
        self.image.fill(Qt.GlobalColor.white)
        self.setFixedSize(self.image.size())
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)
        self.setMouseTracking(True)
        self.color = QColor('#222222')
        self.size = 12
        self.eraser = False
        self.drawing = False
        self.input_kind = None
        self.last = None
        self.ignore_mouse = False
        self.hover_position = None
        self.hover_pressure = 1.0
        self._before_stroke = None
        self._stroke_bounds = None
        self._undo = []
        self._redo = []
        self._enforce_cursor()

    def _enforce_cursor(self):
        # Wayland may restore the mouse arrow after window-state transitions.
        self.setCursor(Qt.CursorShape.BlankCursor)

    def enterEvent(self, event):
        self._enforce_cursor()
        super().enterEvent(event)

    def event(self, event):
        if event.type() in (QEvent.Type.WindowActivate, QEvent.Type.Show,
                            QEvent.Type.WindowStateChange):
            QTimer.singleShot(0, self._enforce_cursor)
        return super().event(event)

    def cursor_rect(self, pos=None):
        pos = self.hover_position if pos is None else pos
        if pos is None:
            return QRectF()
        diameter = self.size if self.eraser else self.size * (0.15 + 0.85 * self.hover_pressure)
        radius = max(3.0, diameter / 2.0)
        return QRectF(pos.x() - radius - 4, pos.y() - radius - 4,
                      2 * radius + 8, 2 * radius + 8)

    def show_hover(self, pos, pressure=None):
        self._enforce_cursor()
        old = self.cursor_rect()
        self.hover_position = QPointF(pos)
        if pressure is not None:
            self.hover_pressure = max(0.0, min(1.0, pressure))
        self.update(old.toAlignedRect())
        self.update(self.cursor_rect().toAlignedRect())

    def refresh_cursor(self):
        self._enforce_cursor()
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
                radius = diameter / 2.0
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
                painter.drawEllipse(center, radius, radius)
                painter.setPen(QPen(QColor(35, 35, 35, 235), 1))
                painter.drawEllipse(center, radius, radius)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 235))
                painter.drawEllipse(center, 2.5, 2.5)
                painter.setBrush(QColor(25, 25, 25, 235))
                painter.drawEllipse(center, 1.3, 1.3)

    def _begin_stroke(self, kind):
        if self.drawing:
            return
        self.drawing = True
        self.input_kind = kind
        self.last = None
        # Temporary snapshot only; history stores cropped affected rectangles.
        self._before_stroke = self.image.copy()
        self._stroke_bounds = QRectF()

    def _include_point(self, point, width):
        r = max(2.0, width / 2.0 + 3)
        rect = QRectF(point.x() - r, point.y() - r, 2 * r, 2 * r)
        self._stroke_bounds = (self._stroke_bounds.united(rect)
                               if not self._stroke_bounds.isNull() else rect)

    def stroke(self, point, pressure, tablet):
        pressure = max(0.0, min(1.0, pressure))
        width = self.size * (0.15 + 0.85 * pressure) if tablet else self.size
        color = QColor(Qt.GlobalColor.white) if self.eraser else self.color
        self._include_point(point, width)
        if self.last is not None:
            self._include_point(self.last, self.size)
        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if self.last is None:
            painter.drawPoint(point)
        else:
            painter.drawLine(self.last, point)
        painter.end()
        self.last = QPointF(point)
        self.update(self._stroke_bounds.toAlignedRect())

    def _push_history(self, rect, before, after):
        if before == after:
            return
        self._undo.append((rect, before, after))
        self._redo.clear()
        self._trim_history()
        self.history_changed.emit(bool(self._undo), bool(self._redo))

    def _trim_history(self):
        def cost(stack):
            return sum((b.sizeInBytes() + a.sizeInBytes()) for _, b, a in stack)
        while len(self._undo) > self.MAX_UNDO_STEPS or (len(self._undo) > 1 and
                cost(self._undo) + cost(self._redo) > self.MAX_UNDO_BYTES):
            self._undo.pop(0)
        while self._redo and cost(self._undo) + cost(self._redo) > self.MAX_UNDO_BYTES:
            self._redo.pop(0)

    def _end_stroke(self):
        if not self.drawing:
            return
        if self._before_stroke is not None and not self._stroke_bounds.isNull():
            rect = self._stroke_bounds.toAlignedRect().intersected(self.image.rect())
            if not rect.isEmpty():
                self._push_history(rect, self._before_stroke.copy(rect), self.image.copy(rect))
        self._before_stroke = None
        self._stroke_bounds = None
        self.drawing = False
        self.input_kind = None
        self.last = None

    def _restore_patch(self, rect, patch):
        painter = QPainter(self.image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(rect.topLeft(), patch)
        painter.end()
        self.update(rect)

    def undo(self):
        if self.drawing:
            return
        if self._undo:
            item = self._undo.pop()
            self._restore_patch(item[0], item[1])
            self._redo.append(item)
            self.history_changed.emit(bool(self._undo), bool(self._redo))

    def redo(self):
        if self.drawing:
            return
        if self._redo:
            item = self._redo.pop()
            self._restore_patch(item[0], item[2])
            self._undo.append(item)
            self.history_changed.emit(bool(self._undo), bool(self._redo))

    def tabletEvent(self, event):
        typ = event.type()
        pressure = float(event.pressure())
        self.show_hover(event.position(), pressure if self.drawing else 1.0)
        device = event.pointingDevice()
        name = device.name() if device else 'Unknown tablet'
        if typ == QEvent.Type.TabletPress:
            self.ignore_mouse = True
            self._begin_stroke('tablet')
            self.stroke(event.position(), pressure, True)
        elif typ == QEvent.Type.TabletMove and self.drawing and self.input_kind == 'tablet':
            self.stroke(event.position(), pressure, True)
        elif typ == QEvent.Type.TabletRelease:
            if self.drawing and self.input_kind == 'tablet':
                self.stroke(event.position(), pressure, True)
                self._end_stroke()
            self.ignore_mouse = False
        self.diagnostic.emit(f'TABLET: {name}  |  pressure: {pressure:.3f}  |  '
                             f'tilt: {event.xTilt():.0f}, {event.yTilt():.0f}  |  {typ.name}')
        event.accept()

    def mousePressEvent(self, event):
        self.show_hover(event.position(), 1.0)
        if not self.ignore_mouse and event.button() == Qt.MouseButton.LeftButton:
            self._begin_stroke('mouse')
            self.stroke(event.position(), 1.0, False)
            self.diagnostic.emit('MOUSE input (fixed width; no pressure)')
        event.accept()

    def mouseMoveEvent(self, event):
        if not self.ignore_mouse:
            self.show_hover(event.position(), 1.0)
        if (not self.ignore_mouse and self.drawing and self.input_kind == 'mouse'
                and event.buttons() & Qt.MouseButton.LeftButton):
            self.stroke(event.position(), 1.0, False)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.input_kind == 'mouse':
            self._end_stroke()
        event.accept()

    def clear(self):
        if self.drawing:
            return
        before = self.image.copy()
        self.image.fill(Qt.GlobalColor.white)
        self._push_history(self.image.rect(), before, self.image.copy())
        self.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Linux Animation Studio - Tablet Prototype 0.3')
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
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 80)
        self.slider.setValue(self.canvas.size)
        self.slider.setMaximumWidth(140)
        self.slider.valueChanged.connect(self.change_size)
        bar.addWidget(self.slider)

        self.undo_button = QPushButton('Undo')
        self.undo_button.clicked.connect(self.canvas.undo)
        self.undo_button.setEnabled(False)
        bar.addWidget(self.undo_button)
        self.redo_button = QPushButton('Redo')
        self.redo_button.clicked.connect(self.canvas.redo)
        self.redo_button.setEnabled(False)
        bar.addWidget(self.redo_button)
        self.canvas.history_changed.connect(self.update_history_buttons)

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
        # Avoid stale arrow cursor over the scroll viewport when maximizing.
        scroll.viewport().setCursor(Qt.CursorShape.BlankCursor)
        layout.addWidget(scroll)
        layout.addWidget(self.status)
        self.setCentralWidget(center)

        self.add_shortcut('Ctrl+Z', self.canvas.undo)
        self.add_shortcut('Ctrl+Shift+Z', self.canvas.redo)
        self.add_shortcut('Ctrl+Y', self.canvas.redo)
        self.add_shortcut('[', lambda: self.slider.setValue(self.slider.value() - 1))
        self.add_shortcut(']', lambda: self.slider.setValue(self.slider.value() + 1))
        self.add_shortcut('Ctrl+S', self.export_png)

    def add_shortcut(self, sequence, callback):
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(callback)

    def update_history_buttons(self, can_undo, can_redo):
        self.undo_button.setEnabled(can_undo)
        self.redo_button.setEnabled(can_redo)

    def change_size(self, size):
        old = self.canvas.cursor_rect()
        self.canvas.size = size
        self.canvas.update(old.toAlignedRect())
        self.canvas.refresh_cursor()

    def toggle_eraser(self, checked):
        self.canvas.eraser = checked
        self.erase_button.setText('Eraser: ON' if checked else 'Eraser: OFF')
        old = self.canvas.cursor_rect()
        self.canvas.update(old.toAlignedRect())
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
