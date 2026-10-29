"""Linux Animation Studio v0.4: pressure-sensitive raster layers and .las projects."""
import io
import json
import sys
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QColorDialog, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSlider, QVBoxLayout, QWidget, QInputDialog,
)

WIDTH, HEIGHT = 1200, 800
IMAGE_FORMAT = QImage.Format.Format_ARGB32_Premultiplied
PROJECT_VERSION = 1
MAX_STEPS = 50
MAX_HISTORY_BYTES = 96 * 1024 * 1024


def transparent_image(width=WIDTH, height=HEIGHT):
    img = QImage(width, height, IMAGE_FORMAT)
    img.fill(Qt.GlobalColor.transparent)
    return img


def png_bytes(image):
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, 'PNG'):
        raise OSError('Could not encode PNG')
    buffer.close()
    return bytes(data)


def image_from_bytes(data, width, height):
    img = QImage.fromData(data, 'PNG')
    if img.isNull() or img.width() != width or img.height() != height:
        raise ValueError('Layer image missing or has an unexpected size')
    return img.convertToFormat(IMAGE_FORMAT)


@dataclass
class Layer:
    id: str
    name: str
    image: QImage
    visible: bool = True


class Canvas(QWidget):
    diagnostic = Signal(str)
    history_changed = Signal(bool, bool)
    document_changed = Signal()
    dirty_changed = Signal()

    def __init__(self):
        super().__init__()
        self.width_px, self.height_px = WIDTH, HEIGHT
        self.layers = [Layer(uuid.uuid4().hex, 'Layer 1', transparent_image())]
        self.active_id = self.layers[0].id
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
        self._stroke_layer_id = None
        self._undo = []
        self._redo = []
        self.dirty = False
        self.setFixedSize(WIDTH, HEIGHT)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)
        self._enforce_cursor()

    def _enforce_cursor(self):
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

    def active_layer(self):
        return next((x for x in self.layers if x.id == self.active_id), None)

    def layer_by_id(self, layer_id):
        return next((x for x in self.layers if x.id == layer_id), None)

    def composite(self, white_background=False):
        image = QImage(self.width_px, self.height_px, IMAGE_FORMAT)
        image.fill(Qt.GlobalColor.white if white_background else Qt.GlobalColor.transparent)
        painter = QPainter(image)
        for layer in self.layers:  # bottom-to-top
            if layer.visible:
                painter.drawImage(0, 0, layer.image)
        painter.end()
        return image

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.GlobalColor.white)
        for layer in self.layers:
            if layer.visible:
                p.drawImage(0, 0, layer.image)
        if self.hover_position is not None:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            diameter = self.size if self.eraser else self.size * (0.15 + 0.85 * self.hover_pressure)
            center = self.hover_position
            if self.eraser:
                r = diameter / 2.0
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(255, 255, 255, 220), 2))
                p.drawEllipse(center, r, r)
                p.setPen(QPen(QColor(35, 35, 35, 235), 1))
                p.drawEllipse(center, r, r)
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 235))
                p.drawEllipse(center, 2.5, 2.5)
                p.setBrush(QColor(25, 25, 25, 235))
                p.drawEllipse(center, 1.3, 1.3)
        p.end()

    def _mark_dirty(self):
        self.dirty = True
        self.dirty_changed.emit()

    def _notify_layers(self):
        self.document_changed.emit()
        self.update()
        self._mark_dirty()

    def _push(self, command):
        self._undo.append(command)
        self._redo.clear()
        self._trim_history()
        self.history_changed.emit(bool(self._undo), bool(self._redo))
        self._mark_dirty()

    def _history_cost(self):
        total = 0
        for cmd in self._undo + self._redo:
            if cmd['type'] == 'patch':
                total += cmd['before'].sizeInBytes() + cmd['after'].sizeInBytes()
            elif cmd['type'] in ('add', 'remove'):
                total += cmd['layer'].image.sizeInBytes()
        return total

    def _trim_history(self):
        while len(self._undo) > MAX_STEPS or (len(self._undo) > 1 and
                                              self._history_cost() > MAX_HISTORY_BYTES):
            self._undo.pop(0)
        while self._redo and self._history_cost() > MAX_HISTORY_BYTES:
            self._redo.pop(0)

    def _begin_stroke(self, kind):
        if self.drawing:
            return
        layer = self.active_layer()
        if layer is None or not layer.visible:
            self.diagnostic.emit('Select a visible layer to draw.')
            return
        self.drawing = True
        self.input_kind = kind
        self.last = None
        self._stroke_layer_id = layer.id
        self._before_stroke = layer.image.copy()
        self._stroke_bounds = QRectF()

    def _include_point(self, point, width):
        r = max(2.0, width / 2.0 + 3)
        rect = QRectF(point.x() - r, point.y() - r, 2 * r, 2 * r)
        self._stroke_bounds = self._stroke_bounds.united(rect) if not self._stroke_bounds.isNull() else rect

    def stroke(self, point, pressure, tablet):
        if not self.drawing:
            return
        layer = self.layer_by_id(self._stroke_layer_id)
        if layer is None:
            return
        pressure = max(0.0, min(1.0, pressure))
        width = self.size * (0.15 + 0.85 * pressure) if tablet else self.size
        self._include_point(point, width)
        if self.last is not None:
            self._include_point(self.last, self.size)
        painter = QPainter(layer.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.eraser:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            pen = QPen(QColor(0, 0, 0, 255), width, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        else:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(self.color, width, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if self.last is None:
            painter.drawPoint(point)
        else:
            painter.drawLine(self.last, point)
        painter.end()
        self.last = QPointF(point)
        self.update(self._stroke_bounds.toAlignedRect())

    def _end_stroke(self):
        if not self.drawing:
            return
        layer = self.layer_by_id(self._stroke_layer_id)
        if layer is not None and self._before_stroke is not None and not self._stroke_bounds.isNull():
            rect = self._stroke_bounds.toAlignedRect().intersected(layer.image.rect())
            if not rect.isEmpty():
                before = self._before_stroke.copy(rect)
                after = layer.image.copy(rect)
                if before != after:
                    self._push(dict(type='patch', id=layer.id, rect=rect,
                                    before=before, after=after))
        self.drawing = False
        self.input_kind = None
        self.last = None
        self._before_stroke = None
        self._stroke_bounds = None
        self._stroke_layer_id = None

    def _apply(self, cmd, forward):
        typ = cmd['type']
        if typ == 'patch':
            layer = self.layer_by_id(cmd['id'])
            if layer is None:
                return
            p = QPainter(layer.image)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            p.drawImage(cmd['rect'].topLeft(), cmd['after'] if forward else cmd['before'])
            p.end()
        elif typ in ('add', 'remove'):
            insert = (typ == 'add') == forward
            if insert:
                self.layers.insert(min(cmd['index'], len(self.layers)), cmd['layer'])
                self.active_id = cmd['layer'].id
            else:
                self.layers = [x for x in self.layers if x.id != cmd['layer'].id]
                self.active_id = cmd['previous_active'] if self.layer_by_id(cmd['previous_active']) else self.layers[-1].id
        elif typ == 'property':
            layer = self.layer_by_id(cmd['id'])
            if layer:
                setattr(layer, cmd['field'], cmd['after'] if forward else cmd['before'])
        elif typ == 'move':
            layer = self.layer_by_id(cmd['id'])
            if layer:
                self.layers.remove(layer)
                self.layers.insert(cmd['after'] if forward else cmd['before'], layer)
        self.document_changed.emit()
        self.update()
        self._mark_dirty()

    def undo(self):
        if self.drawing or not self._undo:
            return
        cmd = self._undo.pop()
        self._apply(cmd, False)
        self._redo.append(cmd)
        self.history_changed.emit(bool(self._undo), bool(self._redo))

    def redo(self):
        if self.drawing or not self._redo:
            return
        cmd = self._redo.pop()
        self._apply(cmd, True)
        self._undo.append(cmd)
        self.history_changed.emit(bool(self._undo), bool(self._redo))

    def new_layer(self):
        if self.drawing:
            return
        index = next((i for i, x in enumerate(self.layers) if x.id == self.active_id), len(self.layers)-1) + 1
        layer = Layer(uuid.uuid4().hex, f'Layer {len(self.layers)+1}', transparent_image(self.width_px, self.height_px))
        cmd = dict(type='add', layer=layer, index=index, previous_active=self.active_id)
        self._apply(cmd, True)
        self._push(cmd)

    def delete_layer(self):
        if self.drawing or len(self.layers) <= 1:
            self.diagnostic.emit('At least one layer must remain.')
            return
        layer = self.active_layer()
        index = self.layers.index(layer)
        fallback = self.layers[index-1].id if index > 0 else self.layers[1].id
        cmd = dict(type='remove', layer=layer, index=index, previous_active=fallback)
        self._apply(cmd, True)
        self._push(cmd)

    def rename_layer(self, text):
        layer = self.active_layer()
        if not layer or not text.strip() or layer.name == text.strip():
            return
        cmd = dict(type='property', id=layer.id, field='name', before=layer.name, after=text.strip())
        self._apply(cmd, True)
        self._push(cmd)

    def toggle_visibility(self):
        layer = self.active_layer()
        if layer is None:
            return
        cmd = dict(type='property', id=layer.id, field='visible', before=layer.visible, after=not layer.visible)
        self._apply(cmd, True)
        self._push(cmd)

    def move_layer(self, offset):
        if self.drawing:
            return
        layer = self.active_layer()
        old = self.layers.index(layer)
        new = old + offset
        if new < 0 or new >= len(self.layers):
            return
        cmd = dict(type='move', id=layer.id, before=old, after=new)
        self._apply(cmd, True)
        self._push(cmd)

    def select_layer(self, layer_id):
        if not self.drawing and self.layer_by_id(layer_id):
            self.active_id = layer_id
            self.document_changed.emit()

    def clear(self):
        if self.drawing:
            return
        layer = self.active_layer()
        if not layer:
            return
        before = layer.image.copy()
        after = transparent_image(self.width_px, self.height_px)
        if before == after:
            return
        layer.image = after
        self._push(dict(type='patch', id=layer.id, rect=layer.image.rect(), before=before, after=after.copy()))
        self.update()

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
        self.diagnostic.emit(f'TABLET: {name} | pressure: {pressure:.3f} | tilt: '
                             f'{event.xTilt():.0f}, {event.yTilt():.0f} | {typ.name}')
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

    def save_project(self, path):
        manifest = dict(format='linux-animation-studio', version=PROJECT_VERSION,
                        width=self.width_px, height=self.height_px,
                        active_layer=self.active_id,
                        layers=[dict(id=x.id, name=x.name, visible=x.visible,
                                     file=f'layers/{x.id}.png') for x in self.layers])
        path = Path(path)
        temporary = path.with_name(path.name + '.tmp')
        try:
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('manifest.json', json.dumps(manifest, indent=2))
                for layer in self.layers:
                    archive.writestr(f'layers/{layer.id}.png', png_bytes(layer.image))
                archive.writestr('preview.png', png_bytes(self.composite(True)))
            temporary.replace(path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        self.dirty = False
        self.dirty_changed.emit()

    def load_project(self, path):
        # Decode and validate fully before modifying the current document.
        with zipfile.ZipFile(path, 'r') as archive:
            info = json.loads(archive.read('manifest.json'))
            if info.get('format') != 'linux-animation-studio' or info.get('version') != PROJECT_VERSION:
                raise ValueError('Unsupported .las project format/version')
            width, height = int(info['width']), int(info['height'])
            if not (1 <= width <= 8192 and 1 <= height <= 8192):
                raise ValueError('Invalid canvas dimensions')
            entries = info['layers']
            if not isinstance(entries, list) or not 1 <= len(entries) <= 100:
                raise ValueError('Invalid layer list')
            layers = []
            seen = set()
            for entry in entries:
                lid = entry['id']
                if not isinstance(lid, str) or not lid.isalnum() or lid in seen:
                    raise ValueError('Invalid or duplicate layer ID')
                seen.add(lid)
                if entry['file'] != f'layers/{lid}.png':
                    raise ValueError('Invalid layer asset path')
                image = image_from_bytes(archive.read(entry['file']), width, height)
                layers.append(Layer(lid, str(entry['name']), image, bool(entry['visible'])))
            active_id = info.get('active_layer')
            if active_id not in seen:
                active_id = layers[-1].id
        self.width_px, self.height_px = width, height
        self.layers = layers
        self.active_id = active_id
        self.setFixedSize(width, height)
        self._undo.clear()
        self._redo.clear()
        self.history_changed.emit(False, False)
        self.dirty = False
        self.dirty_changed.emit()
        self.document_changed.emit()
        self.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project_path = None
        self.resize(1220, 880)
        root = QWidget()
        vertical = QVBoxLayout(root)
        toolbar = QHBoxLayout()
        self.canvas = Canvas()
        self.status = QLabel('Wacom stylus ready | Pick a layer and draw.')
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.canvas.diagnostic.connect(self.status.setText)
        self.canvas.dirty_changed.connect(self.refresh_title)
        self.canvas.document_changed.connect(self.refresh_layers)

        def button(text, callback):
            item = QPushButton(text)
            item.clicked.connect(callback)
            toolbar.addWidget(item)
            return item

        button('Color', self.pick_color)
        self.eraser_button = button('Eraser: OFF', self.toggle_eraser)
        self.eraser_button.setCheckable(True)
        toolbar.addWidget(QLabel('Size:'))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 80)
        self.slider.setValue(self.canvas.size)
        self.slider.setMaximumWidth(130)
        self.slider.valueChanged.connect(self.change_size)
        toolbar.addWidget(self.slider)
        self.undo_button = button('Undo', self.canvas.undo)
        self.redo_button = button('Redo', self.canvas.redo)
        self.undo_button.setEnabled(False)
        self.redo_button.setEnabled(False)
        self.canvas.history_changed.connect(self.update_history)
        button('Clear Layer', self.canvas.clear)
        button('Open .las', self.open_project)
        button('Save .las', self.save_project)
        button('Export PNG', self.export_png)
        vertical.addLayout(toolbar)

        content = QHBoxLayout()
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.viewport().setCursor(Qt.CursorShape.BlankCursor)
        content.addWidget(scroll, 1)
        right = QVBoxLayout()
        right.addWidget(QLabel('Layers (top to bottom)'))
        self.layers_list = QListWidget()
        self.layers_list.setMinimumWidth(180)
        self.layers_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.layers_list.currentItemChanged.connect(self.selection_changed)
        right.addWidget(self.layers_list, 1)
        for label, fn in [('+ Layer', self.canvas.new_layer), ('Delete Layer', self.canvas.delete_layer),
                          ('Rename', self.rename_layer), ('Hide / Show', self.canvas.toggle_visibility),
                          ('Move Up', lambda: self.canvas.move_layer(1)),
                          ('Move Down', lambda: self.canvas.move_layer(-1))]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            right.addWidget(b)
        content.addLayout(right)
        vertical.addLayout(content, 1)
        vertical.addWidget(self.status)
        self.setCentralWidget(root)
        self.refresh_layers()
        self.refresh_title()
        for seq, fn in [('Ctrl+Z', self.canvas.undo), ('Ctrl+Shift+Z', self.canvas.redo),
                        ('Ctrl+Y', self.canvas.redo), ('Ctrl+S', self.save_project),
                        ('Ctrl+Shift+S', self.save_project_as), ('Ctrl+O', self.open_project),
                        ('[', lambda: self.slider.setValue(self.slider.value()-1)),
                        (']', lambda: self.slider.setValue(self.slider.value()+1))]:
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(fn)

    def refresh_title(self):
        name = Path(self.project_path).name if self.project_path else 'Untitled.las'
        self.setWindowTitle(f'Linux Animation Studio v0.4 - {name}{" *" if self.canvas.dirty else ""}')

    def refresh_layers(self):
        self.layers_list.blockSignals(True)
        self.layers_list.clear()
        for layer in reversed(self.canvas.layers):
            item = QListWidgetItem(('● ' if layer.visible else '○ ') + layer.name)
            item.setData(Qt.ItemDataRole.UserRole, layer.id)
            self.layers_list.addItem(item)
            if layer.id == self.canvas.active_id:
                self.layers_list.setCurrentItem(item)
        self.layers_list.blockSignals(False)

    def selection_changed(self, current, previous):
        if current is not None:
            self.canvas.select_layer(current.data(Qt.ItemDataRole.UserRole))

    def rename_layer(self):
        layer = self.canvas.active_layer()
        if layer:
            name, ok = QInputDialog.getText(self, 'Rename Layer', 'Name:', text=layer.name)
            if ok:
                self.canvas.rename_layer(name)

    def update_history(self, undo, redo):
        self.undo_button.setEnabled(undo)
        self.redo_button.setEnabled(redo)

    def change_size(self, size):
        old = self.canvas.cursor_rect()
        self.canvas.size = size
        self.canvas.update(old.toAlignedRect())
        self.canvas.refresh_cursor()

    def toggle_eraser(self, checked):
        self.canvas.eraser = checked
        self.eraser_button.setText('Eraser: ON' if checked else 'Eraser: OFF')
        self.canvas.refresh_cursor()

    def pick_color(self):
        color = QColorDialog.getColor(self.canvas.color, self, 'Choose brush color')
        if color.isValid():
            self.canvas.color = color
            self.eraser_button.setChecked(False)

    def _confirm_discard(self):
        if not self.canvas.dirty:
            return True
        result = QMessageBox.question(self, 'Unsaved artwork',
                                      'Discard unsaved changes?',
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        return result == QMessageBox.StandardButton.Yes

    def open_project(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Open editable project',
                                               str(Path.home()), 'LAS projects (*.las)')
        if not path:
            return
        try:
            self.canvas.load_project(path)
            self.project_path = path
            self.refresh_title()
            self.status.setText(f'Opened: {path}')
        except Exception as exc:
            QMessageBox.critical(self, 'Open failed', str(exc))

    def save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save editable project',
                                               self.project_path or str(Path.home()/'Untitled.las'),
                                               'LAS projects (*.las)')
        if not path:
            return False
        if not path.lower().endswith('.las'):
            path += '.las'
        return self._save_to(path)

    def _save_to(self, path):
        try:
            self.canvas.save_project(path)
            self.project_path = path
            self.refresh_title()
            self.status.setText(f'Saved: {path}')
            return True
        except Exception as exc:
            QMessageBox.critical(self, 'Save failed', str(exc))
            return False

    def save_project(self):
        return self._save_to(self.project_path) if self.project_path else self.save_project_as()

    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export visible layers as PNG',
                                               str(Path.home()/'drawing.png'), 'PNG files (*.png)')
        if not path:
            return
        if not path.lower().endswith('.png'):
            path += '.png'
        ok = self.canvas.composite(True).save(path, 'PNG')
        self.status.setText(('Exported: ' if ok else 'Export failed: ') + path)

    def closeEvent(self, event):
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
