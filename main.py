"""Linux Animation Studio v0.27.1: palette refresh and swatch removal."""
import io
import wave
import time
import os
import math
import random
import shutil
import subprocess
import tempfile
import json
import sys
import platform
import uuid
import zipfile
from dataclasses import dataclass, field
from bisect import bisect_left
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, QCoreApplication, QEvent, QPoint, QPointF, QRect, QRectF, QTimer, QElapsedTimer, Qt, Signal, QUrl
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QPen, QShortcut, QRadialGradient, QTransform, QPixmap, QPainterPath, QPolygonF, QIcon, QLinearGradient
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QApplication, QAbstractSpinBox, QLineEdit, QTextEdit, QPlainTextEdit, QAbstractItemView, QColorDialog, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget, QInputDialog, QSpinBox, QSplitter, QSizePolicy, QDoubleSpinBox, QToolButton, QButtonGroup, QFrame, QCheckBox, QProgressDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QTabWidget, QMenu, QGridLayout,
)

APP_VERSION = "0.27.1"
WIDTH, HEIGHT = 1200, 800
IMAGE_FORMAT = QImage.Format.Format_ARGB32_Premultiplied
PROJECT_VERSION = 6
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


def application_data_root():
    """OS-appropriate application data; keep the established Linux brush path."""
    if sys.platform.startswith('linux'):
        base = Path(os.environ.get('XDG_DATA_HOME') or (Path.home() / '.local' / 'share'))
        return base / 'linux-animation-studio'
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    if location:
        base = Path(location)
        # Qt may already append the application name; never append it twice.
        return base if base.name.lower() == 'linuxanimationstudio' else base / 'LinuxAnimationStudio'
    return Path.home() / '.linux-animation-studio'


BRUSH_ROOT = application_data_root() / 'brushes'


def resolve_ffmpeg():
    """Look for FFmpeg on PATH, in an override, or beside a packaged executable."""
    override = os.environ.get('LAS_FFMPEG_PATH')
    candidates = []
    if override:
        candidates.append(Path(override).expanduser())
    exe_name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
    candidates.append(Path(sys.executable).resolve().parent / exe_name)
    candidates.append(Path(__file__).resolve().parent / exe_name)
    for candidate in candidates:
        if candidate.is_file() and (os.name == 'nt' or os.access(candidate, os.X_OK)):
            return str(candidate)
    return shutil.which('ffmpeg')



def load_custom_brushes():
    """Load user-created brushes; ignore incomplete or malformed entries."""
    brushes = {}
    if not BRUSH_ROOT.exists():
        return brushes
    for info in BRUSH_ROOT.glob('*.json'):
        try:
            meta = json.loads(info.read_text(encoding='utf-8'))
            ident = info.stem
            tip = QImage(str(BRUSH_ROOT / (ident + '.png')))
            if tip.isNull() or tip.width() > 512 or tip.height() > 512:
                continue
            brushes[ident] = {'name': str(meta['name']), 'mode': meta['mode'] if meta.get('mode') in ('color','tint') else 'color',
                              'spacing': max(0.01, min(4.0, float(meta.get('spacing', .30)))),
                              'size': max(1, min(500, int(meta.get('size', 48)))),
                              'opacity': max(1, min(100, int(meta.get('opacity', 100)))),
                              'follow_direction': bool(meta.get('follow_direction', False)),
                              'rotation_jitter': max(0, min(180, int(meta.get('rotation_jitter', 0)))),
                              'scatter': max(0, min(200, int(meta.get('scatter', 0)))),
                              'pressure_size': max(0, min(100, int(meta.get('pressure_size', 100)))),
                              'pressure_opacity': max(0, min(100, int(meta.get('pressure_opacity', 0)))),
                              'tip': tip.convertToFormat(IMAGE_FORMAT)}
        except (ValueError, KeyError, OSError, TypeError):
            continue
    return brushes


def save_custom_brush(ident, brush):
    BRUSH_ROOT.mkdir(parents=True, exist_ok=True)
    tip_path = BRUSH_ROOT / (ident + '.png')
    if not brush['tip'].save(str(tip_path), 'PNG'):
        raise OSError('Unable to save custom brush tip')
    metadata = {k: brush[k] for k in ('name','mode','spacing','size','opacity', 'follow_direction', 'rotation_jitter', 'scatter', 'pressure_size', 'pressure_opacity')}
    (BRUSH_ROOT / (ident + '.json')).write_text(json.dumps(metadata, indent=2), encoding='utf-8')


@dataclass
class Layer:
    id: str
    name: str
    image: QImage
    visible: bool = True
    opacity: int = 100
    mode: str = "animated"  # animated cels or one shared static image
    cel_id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class MotionObject:
    id: str
    name: str
    image: QImage
    # frame number -> (offset x, offset y, scale percent, rotation degrees)
    keys: dict


def interpolated_transform(keys, frame):
    """Linear interpolation, with endpoint holds; pure Python and unit-testable."""
    if not keys:
        return (0.0, 0.0, 100.0, 0.0)
    indices = sorted(keys)
    if frame <= indices[0]:
        return tuple(keys[indices[0]])
    if frame >= indices[-1]:
        return tuple(keys[indices[-1]])
    j = bisect_left(indices, frame)
    left, right = indices[j - 1], indices[j]
    t = (frame - left) / (right - left)
    return tuple(a + (b - a) * t for a, b in zip(keys[left], keys[right]))


class Canvas(QWidget):
    diagnostic = Signal(str)
    history_changed = Signal(bool, bool)
    document_changed = Signal()
    dirty_changed = Signal()
    frames_changed = Signal()
    playhead_changed = Signal(int)
    motion_changed = Signal()

    def __init__(self):
        super().__init__()
        self.width_px, self.height_px = WIDTH, HEIGHT
        self.layers = [Layer(uuid.uuid4().hex, 'Layer 1', transparent_image())]
        self.active_id = self.layers[0].id
        self.color = QColor('#000000')
        self.size = 12
        self.custom_brushes = load_custom_brushes()
        self.active_custom_brush = None
        self._stamp_distance = 0.0
        self._stamp_rng = random.Random()
        self._stamp_cache = {}
        self.brush_preset = 'Round'
        self.brush_settings = {name: {'size': size, 'opacity': opacity} for name, size, opacity in [('Round', 12, 100), ('Pencil', 9, 55), ('Ink', 6, 100), ('Airbrush', 32, 22)]}
        self.eraser = False
        self.eraser_size = 48
        self.zoom = 1.0
        self.tool = 'brush'  # brush, eraser, select, move
        self.selection = None  # Bounding QRect in document pixels
        self.selection_path = None  # Actual selected geometry, with antialiased edges
        self.selection_mask = None  # ARGB mask shared by raster operations
        self.selection_mode = 'rectangle'
        self.lasso_points = []
        self.lasso_preview = None
        self._polygon_last_click = None
        self.drag_origin = None
        self.drag_rect = None
        self.move_source = None
        self.move_preview = None
        self.move_offset = QPoint(0, 0)
        self.move_layer_id = None
        self.transform_session = None
        self.transform_drag = None
        self.transform_motion_mode = False
        self.drawing = False
        self.input_kind = None
        self.last = None
        self.ignore_mouse = False
        self.hover_position = None
        self.hover_pressure = 1.0
        self._before_stroke = None
        self._multi_stroke_before = None
        self._multi_stroke_samples = []
        self._stroke_bounds = None
        self._stroke_layer_id = None
        self._undo = []
        self._redo = []
        self.dirty = False
        self.frames = [self.layers]
        self.motion_objects = []
        self.active_motion_id = None
        self.frame_index = 0
        self.fps = 12
        self.onion_enabled = False
        self.onion_opacity = 35
        self.onion_previous = 1
        self.onion_next = 1
        self.playing = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(WIDTH, HEIGHT)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)
        self._enforce_cursor()

    def set_zoom(self, zoom):
        self.zoom = max(0.25, min(8.0, float(zoom)))
        self.setFixedSize(round(self.width_px * self.zoom), round(self.height_px * self.zoom))
        self.update()

    def _enforce_cursor(self):
        # Transform uses the standard OS arrow; other tools draw canvas overlays.
        shape = (Qt.CursorShape.ArrowCursor if self.tool == "transform"
                 else Qt.CursorShape.BlankCursor)
        self.setCursor(shape)

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
        diameter = (self.size if self.tool == "eraser" else self.size * (0.15 + 0.85 * self.hover_pressure)) if self.tool in ("brush", "eraser") else 8
        radius = max(3.0, diameter / 2.0)
        return QRectF(pos.x() - radius - 4, pos.y() - radius - 4,
                      2 * radius + 8, 2 * radius + 8)

    def show_hover(self, pos, pressure=None):
        self._enforce_cursor()
        old = self.cursor_rect()
        self.hover_position = QPointF(pos)
        if pressure is not None:
            self.hover_pressure = max(0.0, min(1.0, pressure))
        self.update()

    def refresh_cursor(self):
        self._enforce_cursor()
        self.update()

    def leaveEvent(self, event):
        old = self.cursor_rect()
        self.hover_position = None
        self.update()
        super().leaveEvent(event)

    def active_layer(self):
        return next((x for x in self.layers if x.id == self.active_id), None)

    def layer_by_id(self, layer_id):
        return next((x for x in self.layers if x.id == layer_id), None)

    def active_motion(self):
        return next((obj for obj in self.motion_objects if obj.id == self.active_motion_id), None)

    def draw_motion_objects(self, painter, index):
        # The source is immutable; transforms happen only while compositing.
        for obj in self.motion_objects:
            dx, dy, percent, degrees = interpolated_transform(obj.keys, index)
            session = self.transform_session
            if (session and session['kind'] == 'motion' and session['id'] == obj.id
                    and index == self.frame_index):
                dx, dy, percent, degrees = session['values']
            painter.save()
            cx, cy = self.width_px / 2.0, self.height_px / 2.0
            painter.translate(cx + dx, cy + dy)
            painter.rotate(degrees)
            painter.scale(percent / 100.0, percent / 100.0)
            painter.drawImage(QPointF(-cx, -cy), obj.image)
            painter.restore()

    def make_motion_from_layer(self):
        if self.playing or self.drawing or self.drag_origin is not None:
            raise ValueError('Stop drawing/playback before making a motion object')
        layer = self.active_layer()
        if layer is None:
            raise ValueError('Select a layer first')
        # Moving the pixels into an independent object avoids drawing them twice.
        # We deliberately do not change other animation frames.
        if len(self.motion_objects) >= 20:
            raise ValueError('The prototype supports up to 20 motion objects')
        obj = MotionObject(uuid.uuid4().hex, layer.name + ' (motion)', layer.image.copy(),
                           {self.frame_index: (0.0, 0.0, 100.0, 0.0)})
        layer.image = transparent_image(self.width_px, self.height_px)
        layer.cel_id = uuid.uuid4().hex
        self.motion_objects.append(obj)
        self.active_motion_id = obj.id
        self._undo.clear()
        self._redo.clear()
        self.history_changed.emit(False, False)
        self._mark_dirty()
        self._notify_layers()
        self.motion_changed.emit()
        return obj

    def set_motion_key(self, x, y, scale, angle):
        obj = self.active_motion()
        if obj is None:
            raise ValueError('Create or select a motion object first')
        if self.playing:
            raise ValueError('Pause playback before editing keyframes')
        before = obj.keys.get(self.frame_index)
        after = (float(x), float(y), float(scale), float(angle))
        if before == after:
            return
        cmd = dict(type='motion_key', id=obj.id, frame=self.frame_index,
                   before=before, after=after)
        self._apply(cmd, True)
        self._push(cmd)

    def delete_motion_key(self):
        obj = self.active_motion()
        if obj is not None and self.frame_index in obj.keys and len(obj.keys) > 1:
            cmd = dict(type='motion_key', id=obj.id, frame=self.frame_index,
                       before=obj.keys[self.frame_index], after=None)
            self._apply(cmd, True)
            self._push(cmd)

    def composite(self, white_background=False):
        image = QImage(self.width_px, self.height_px, IMAGE_FORMAT)
        image.fill(Qt.GlobalColor.white if white_background else Qt.GlobalColor.transparent)
        painter = QPainter(image)
        for layer in self.layers:  # bottom-to-top
            if layer.visible:
                painter.setOpacity(layer.opacity / 100.0)
                painter.drawImage(0, 0, layer.image)
                painter.setOpacity(1.0)
        self.draw_motion_objects(painter, self.frame_index)
        painter.end()
        return image

    def _tinted_neighbor(self, index, tint):
        # Compositing is read-only; onion skins never touch underlying layer images.
        if not 0 <= index < len(self.frames):
            return None
        source = QImage(self.width_px, self.height_px, IMAGE_FORMAT)
        source.fill(Qt.GlobalColor.transparent)
        painter = QPainter(source)
        for layer in self.frames[index]:
            if layer.visible and layer.mode == "animated":
                painter.setOpacity(layer.opacity / 100.0)
                painter.drawImage(0, 0, layer.image)
        self.draw_motion_objects(painter, index)
        painter.end()
        painter = QPainter(source)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(source.rect(), tint)
        painter.end()
        return source

    def paintEvent(self, event):
        p = QPainter(self)
        p.scale(self.zoom, self.zoom)
        p.fillRect(QRect(0, 0, self.width_px, self.height_px), Qt.GlobalColor.white)
        for layer in self.layers:
            if layer.visible:
                p.setOpacity(layer.opacity / 100.0)
                p.drawImage(0, 0, layer.image)
                p.setOpacity(1.0)
        self.draw_motion_objects(p, self.frame_index)
        session = self.transform_session
        if session and session['kind'] == 'raster':
            # Rebuild the flattened preview using a temporary copy. Source artwork
            # remains untouched until Apply; each move reuses the original snapshot.
            layer = self.layer_by_id(session['id'])
            if layer is not None:
                preview_layer = self._transformed_layer_image(session)
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                p.setOpacity(1.0)
                p.fillRect(QRect(0, 0, self.width_px, self.height_px), Qt.GlobalColor.white)
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                for drawn_layer in self.layers:
                    if drawn_layer.visible:
                        p.setOpacity(drawn_layer.opacity / 100.0)
                        p.drawImage(0, 0, preview_layer if drawn_layer.id == layer.id else drawn_layer.image)
                p.setOpacity(1.0)
                self.draw_motion_objects(p, self.frame_index)
        if self.move_preview is not None and self.move_layer_id is not None:
            layer = self.layer_by_id(self.move_layer_id)
            if layer is not None:
                # Preview the source pixels at their destination without permanently changing the layer.
                preview_layer = layer.image.copy()
                ghost = QPainter(preview_layer)
                self._clear_selected(ghost, self.move_source_rect)
                ghost.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                ghost.drawImage(self.move_preview.topLeft(), self.move_source)
                ghost.end()
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                p.setOpacity(1.0)
                p.fillRect(self.rect(), Qt.GlobalColor.white)
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                for drawn_layer in self.layers:
                    if drawn_layer.visible:
                        p.setOpacity(drawn_layer.opacity / 100.0)
                        p.drawImage(0, 0, preview_layer if drawn_layer.id == layer.id else drawn_layer.image)
                p.setOpacity(1.0)
                self.draw_motion_objects(p, self.frame_index)
        if self.onion_enabled and not self.playing:
            # Composite distant ghosts first, near ghosts last; do not modify source cels.
            for direction, count, tint in ((-1, self.onion_previous, QColor('#d65c66')),
                                           (1, self.onion_next, QColor('#35a87c'))):
                for distance in range(count, 0, -1):
                    neighbor = self._tinted_neighbor(self.frame_index + direction * distance, tint)
                    if neighbor is not None:
                        p.setOpacity((self.onion_opacity / 100.0) * (1.0 / distance))
                        p.drawImage(0, 0, neighbor)
            p.setOpacity(1.0)
        outlined = None if self.playing else (self.drag_rect if self.drag_rect is not None else self.selection)
        if outlined is not None and not outlined.isEmpty() and (self.selection_path is None or self.drag_rect is not None):
            p.setPen(QPen(QColor(255,255,255), 1, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(outlined)
            p.setPen(QPen(QColor(10,10,10), 1, Qt.PenStyle.DotLine))
            p.drawRect(outlined.adjusted(1,1,-1,-1))
        if self.selection_path is not None and not self.playing:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor('#ffffff'), 1 / self.zoom, Qt.PenStyle.DashLine))
            p.drawPath(self.selection_path)
            p.setPen(QPen(QColor('#191919'), 1 / self.zoom, Qt.PenStyle.DotLine))
            p.drawPath(self.selection_path)
        if self.lasso_preview is not None and not self.playing:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor('#333333'), 1.4 / self.zoom, Qt.PenStyle.DashLine))
            p.drawPath(self.lasso_preview)
            if self.selection_mode == 'polygonal':
                for v in self.lasso_points:
                    p.setBrush(QColor('#ffffff'))
                    p.drawEllipse(v, 3 / self.zoom, 3 / self.zoom)
        if session and not self.playing:
            self._paint_transform_handles(p, session)
        if self.hover_position is not None and not self.playing:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            center = self.hover_position
            if self.tool in ('brush', 'eraser'):
                diameter = self.size if self.tool == 'eraser' else self.size * (0.15 + 0.85 * self.hover_pressure)
                r = max(0.5, diameter / 2.0)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(255, 255, 255, 230), 2.0 / self.zoom))
                p.drawEllipse(center, r, r)
                p.setPen(QPen(QColor(24, 24, 24, 235), 1.0 / self.zoom))
                p.drawEllipse(center, r, r)
                p.setBrush(QColor('#222222'))
                p.drawEllipse(center, 1.1 / self.zoom, 1.1 / self.zoom)
            elif self.tool in ('select', 'move'):
                # View-independent, high contrast cursor glyphs anchored to the pen tip.
                x, y = center.x(), center.y()
                r = 12.0 / self.zoom
                p.setBrush(Qt.BrushStyle.NoBrush)
                for color, pen_width in ((QColor(255,255,255), 3.0 / self.zoom),
                                         (QColor(20,20,25), 1.25 / self.zoom)):
                    p.setPen(QPen(color, pen_width, Qt.PenStyle.SolidLine,
                                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                    if self.tool == 'select':
                        p.drawLine(QPointF(x-r,y), QPointF(x+r,y))
                        p.drawLine(QPointF(x,y-r), QPointF(x,y+r))
                        p.drawEllipse(center, 2.5/self.zoom, 2.5/self.zoom)
                    else:
                        p.drawLine(QPointF(x-r,y),QPointF(x+r,y))
                        p.drawLine(QPointF(x,y-r),QPointF(x,y+r))
                        a = 4.5/self.zoom
                        for sign in (-1,1):
                            p.drawLine(QPointF(x+sign*r,y),QPointF(x+sign*(r-a),y-a))
                            p.drawLine(QPointF(x+sign*r,y),QPointF(x+sign*(r-a),y+a))
                            p.drawLine(QPointF(x,y+sign*r),QPointF(x-a,y+sign*(r-a)))
                            p.drawLine(QPointF(x,y+sign*r),QPointF(x+a,y+sign*(r-a)))
        p.end()

    def begin_transform(self, motion=False):
        """Start a cancellable, non-destructive manipulation session."""
        if self.playing or self.drawing:
            return False
        self.cancel_transform()
        if motion:
            obj = self.active_motion()
            if obj is None:
                self.diagnostic.emit('Select a motion object in the timeline first.')
                return False
            self.transform_session = dict(kind='motion', id=obj.id,
                rect=QRectF(0, 0, self.width_px, self.height_px),
                pivot=QPointF(self.width_px/2, self.height_px/2),
                values=list(interpolated_transform(obj.keys, self.frame_index)),
                original=obj.keys.get(self.frame_index))
        else:
            layer = self.active_layer()
            if layer is None or not layer.visible:
                return False
            rect = self.selection if self.selection else layer.image.rect()
            if rect.isEmpty():
                return False
            self.transform_session = dict(kind='raster', id=layer.id, frame=self.frame_index,
                rect=QRectF(rect), pivot=QPointF(rect.center()),
                source=layer.image.copy(), selection_mask=self.selection_mask.copy() if self.selection_mask is not None else None, offset=QPointF(0, 0), scale=1.0, angle=0.0)
        self.tool = 'transform'
        self._enforce_cursor()
        self.update()
        return True

    def cancel_transform(self):
        self.transform_drag = None
        self.transform_session = None
        self.update()

    def _transform_matrix(self, session):
        pivot = session['pivot']
        matrix = QTransform()
        matrix.translate(pivot.x(), pivot.y())
        matrix.translate(session['offset'].x(), session['offset'].y())
        matrix.rotate(session['angle'])
        matrix.scale(session['scale'], session['scale'])
        matrix.translate(-pivot.x(), -pivot.y())
        return matrix

    def _transformed_layer_image(self, session):
        image = session['source'].copy()
        rect = session['rect'].toAlignedRect()
        crop = session['source'].copy(rect)
        mask = session.get('selection_mask')
        if mask is not None:
            crop = self._masked_crop(session['source'], rect, mask)
        painter = QPainter(image)
        if mask is not None:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            painter.drawImage(0, 0, mask)
        else:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setTransform(self._transform_matrix(session))
        painter.drawImage(rect.topLeft(), crop)
        painter.end()
        return image

    def _transform_handles(self, session):
        if session['kind'] == 'raster':
            mat = self._transform_matrix(session)
            rect = session['rect']
            corners = [mat.map(pt) for pt in (rect.topLeft(),rect.topRight(),rect.bottomRight(),rect.bottomLeft())]
            pivot = mat.map(session['pivot'])
        else:
            x,y,scale,angle = session['values']
            rect = session['rect']
            pivot = QPointF(session['pivot'].x()+x, session['pivot'].y()+y)
            mat=QTransform()
            mat.translate(pivot.x(),pivot.y())
            mat.rotate(angle)
            mat.scale(scale/100,scale/100)
            mat.translate(-session['pivot'].x(),-session['pivot'].y())
            corners=[mat.map(pt) for pt in (rect.topLeft(),rect.topRight(),rect.bottomRight(),rect.bottomLeft())]
        top=QPointF((corners[0].x()+corners[1].x())/2,(corners[0].y()+corners[1].y())/2)
        vx=top.x()-pivot.x();vy=top.y()-pivot.y()
        length=max(1.0,math.hypot(vx,vy))
        rot=QPointF(top.x()+vx/length*28/self.zoom,top.y()+vy/length*28/self.zoom)
        return corners,pivot,rot

    def _paint_transform_handles(self,painter,session):
        corners,pivot,rot=self._transform_handles(session)
        painter.setOpacity(1.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor('#7356be'),1.7/self.zoom,Qt.PenStyle.DashLine))
        for i in range(4): painter.drawLine(corners[i],corners[(i+1)%4])
        painter.setPen(QPen(QColor('#3b285e'),1.3/self.zoom))
        painter.setBrush(QColor('white'))
        radius=5/self.zoom
        for pt in corners: painter.drawRect(QRectF(pt.x()-radius,pt.y()-radius,2*radius,2*radius))
        painter.drawEllipse(rot,radius,radius)
        painter.setBrush(QColor('#eeab36'))
        painter.drawEllipse(pivot,4/self.zoom,4/self.zoom)

    def _transform_press(self,point):
        session=self.transform_session
        if not session:return
        corners,pivot,rot=self._transform_handles(session)
        threshold=13/self.zoom
        mode='move'
        if math.hypot(point.x()-rot.x(),point.y()-rot.y())<threshold: mode='rotate'
        elif math.hypot(point.x()-pivot.x(),point.y()-pivot.y())<threshold: mode='pivot'
        elif min(math.hypot(point.x()-c.x(),point.y()-c.y()) for c in corners)<threshold: mode='scale'
        self.transform_drag=dict(mode=mode,start=QPointF(point),pivot=QPointF(pivot),
            scale=session.get('scale'),angle=session.get('angle'),offset=QPointF(session.get('offset',QPointF())),
            values=list(session.get('values',[])),point_distance=max(1,math.hypot(point.x()-pivot.x(),point.y()-pivot.y())),
            point_angle=math.degrees(math.atan2(point.y()-pivot.y(),point.x()-pivot.x())))

    def _transform_move(self,point):
        session=self.transform_session;drag=self.transform_drag
        if not session or not drag:return
        dx=point.x()-drag['start'].x();dy=point.y()-drag['start'].y()
        mode=drag['mode']
        if session['kind']=='raster':
            if mode=='move':session['offset']=drag['offset']+QPointF(dx,dy)
            elif mode=='pivot':
                session['pivot']+=QPointF(dx,dy);drag['start']=QPointF(point)
            elif mode=='scale':session['scale']=max(.01,min(20,drag['scale']*math.hypot(point.x()-drag['pivot'].x(),point.y()-drag['pivot'].y())/drag['point_distance']))
            elif mode=='rotate':session['angle']=drag['angle']+math.degrees(math.atan2(point.y()-drag['pivot'].y(),point.x()-drag['pivot'].x()))-drag['point_angle']
        else:
            vals=drag['values'][:]
            if mode=='move':vals[0]+=dx;vals[1]+=dy
            elif mode=='pivot':session['pivot']+=QPointF(dx,dy);drag['start']=QPointF(point)
            elif mode=='scale':vals[2]=max(1,min(400,vals[2]*math.hypot(point.x()-drag['pivot'].x(),point.y()-drag['pivot'].y())/drag['point_distance']))
            elif mode=='rotate':vals[3]+=math.degrees(math.atan2(point.y()-drag['pivot'].y(),point.x()-drag['pivot'].x()))-drag['point_angle']
            session['values']=vals
        self.update()

    def apply_transform(self, keep_selection=False):
        session=self.transform_session
        if session is None:return
        if session['kind']=='raster':
            layer=self.layer_by_id(session['id'])
            if layer is not None:
                before=session['source']
                after=self._transformed_layer_image(session)
                multi = (getattr(self, 'multi_edit_enabled', False) and
                         len(getattr(self, 'multi_edit_frames', [])) > 1 and layer.mode == 'animated')
                if multi and before != after:
                    snapshot_before = self._timeline_snapshot()
                    seen = {(layer.id, layer.cel_id)}
                    for index in sorted(set(self.multi_edit_frames)):
                        if not 0 <= index < len(self.frames) or index == session['frame']:
                            continue
                        peer = next((x for x in self.frames[index] if x.id == layer.id), None)
                        if peer is None or peer.mode != 'animated' or (peer.id, peer.cel_id) in seen:
                            continue
                        seen.add((peer.id, peer.cel_id))
                        peer_session = dict(session)
                        peer_session['source'] = peer.image.copy()
                        transformed = self._transformed_layer_image(peer_session)
                        for f in self.frames:
                            for linked in f:
                                if linked.id == peer.id and linked.cel_id == peer.cel_id:
                                    linked.image = transformed
                    for f in self.frames:
                        for linked in f:
                            if linked.id == layer.id and linked.cel_id == layer.cel_id:
                                linked.image = after
                    self._push(dict(type='timeline_snapshot', before=snapshot_before,
                                    after=self._timeline_snapshot()))
                elif before!=after:
                    for f in self.frames:
                        peer = next((x for x in f if x.id == layer.id and x.cel_id == layer.cel_id), None)
                        if peer is not None:
                            peer.image = after
                    self._push(dict(type='patch',id=layer.id,frame=session['frame'],rect=after.rect(),before=before,after=after.copy()))
        else:
            obj=self.active_motion()
            if obj and obj.id==session['id']:
                values=session['values']
                self.set_motion_key(*values)
        self.cancel_transform()
        if session['kind'] == 'raster' and not keep_selection:
            self.deselect()
        self.document_changed.emit()
        self.frames_changed.emit()

    def _mark_dirty(self):
        self.dirty = True
        self.dirty_changed.emit()

    def _notify_layers(self):
        self.document_changed.emit()
        self.update()
        self._mark_dirty()
        self.frames_changed.emit()

    def _push(self, command):
        self._undo.append(command)
        self._redo.clear()
        self._trim_history()
        self.history_changed.emit(bool(self._undo), bool(self._redo))
        self._mark_dirty()
        self.frames_changed.emit()

    def _history_cost(self):
        total = 0
        for cmd in self._undo + self._redo:
            if cmd['type'] == 'patch':
                total += cmd['before'].sizeInBytes() + cmd['after'].sizeInBytes()
            elif cmd['type'] in ('add', 'remove'):
                total += cmd['layer'].image.sizeInBytes()
            elif cmd['type'] in ('frame_add', 'frame_delete'):
                total += sum(layer.image.sizeInBytes() for layer in cmd['layers'] if layer.mode != 'static')
        return total

    def _trim_history(self):
        while len(self._undo) > MAX_STEPS or (len(self._undo) > 1 and
                                              self._history_cost() > MAX_HISTORY_BYTES):
            self._undo.pop(0)
        while self._redo and self._history_cost() > MAX_HISTORY_BYTES:
            self._redo.pop(0)

    def _begin_stroke(self, kind):
        if self.drawing or self.playing:
            return
        layer = self.active_layer()
        if layer is None or not layer.visible:
            self.diagnostic.emit('Select a visible layer to draw.')
            return
        self.drawing = True
        self.input_kind = kind
        self.last = None
        self._stroke_layer_id = layer.id
        self._stroke_frame = self.frame_index
        self._before_stroke = layer.image.copy()
        self._multi_stroke_samples = []
        self._multi_stroke_before = None
        if (getattr(self, 'multi_edit_enabled', False) and
                layer.mode == 'animated' and
                len(getattr(self, 'multi_edit_frames', [])) > 1):
            self._multi_stroke_before = self._timeline_snapshot()
        self._stroke_bounds = QRectF()
        self._stamp_distance = 0.0

    def _include_point(self, point, width):
        r = max(2.0, width / 2.0 + 3)
        rect = QRectF(point.x() - r, point.y() - r, 2 * r, 2 * r)
        self._stroke_bounds = self._stroke_bounds.united(rect) if not self._stroke_bounds.isNull() else rect

    def _custom_tip(self, ident, diameter):
        brush = self.custom_brushes[ident]
        diameter = max(1, min(500, int(round(diameter))))
        key = (ident, diameter, brush['mode'], self.color.name(QColor.NameFormat.HexArgb) if brush['mode'] == 'tint' else '')
        if key not in self._stamp_cache:
            original = brush['tip']
            scaled = original.scaled(diameter, diameter, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
            if brush['mode'] == 'tint':
                tinted = QImage(scaled.size(), IMAGE_FORMAT)
                tinted.fill(Qt.GlobalColor.transparent)
                p = QPainter(tinted)
                p.drawImage(0, 0, scaled)
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                p.fillRect(tinted.rect(), self.color)
                p.end()
                scaled = tinted
            if len(self._stamp_cache) >= 48:
                self._stamp_cache.clear()
            self._stamp_cache[key] = scaled
        return self._stamp_cache[key]

    def _paint_custom_stamp(self, painter, point, width, pressure, direction):
        brush = self.custom_brushes[self.active_custom_brush]
        tip = self._custom_tip(self.active_custom_brush, width)
        angle = (direction if brush['follow_direction'] else 0.0)
        angle += self._stamp_rng.uniform(-brush['rotation_jitter'], brush['rotation_jitter'])
        scatter = width * brush['scatter'] / 100.0
        offset_x = self._stamp_rng.uniform(-scatter, scatter)
        offset_y = self._stamp_rng.uniform(-scatter, scatter)
        opacity_factor = 1.0 - brush['pressure_opacity']/100.0 * (1.0 - pressure)
        painter.save()
        painter.setOpacity(brush['opacity'] / 100.0 * opacity_factor)
        painter.translate(point.x() + offset_x, point.y() + offset_y)
        painter.rotate(angle)
        painter.drawImage(QPointF(-tip.width()/2, -tip.height()/2), tip)
        painter.restore()

    def _stroke_custom(self, painter, point, width, pressure, tablet):
        brush = self.custom_brushes[self.active_custom_brush]
        # Distances are in canvas pixels and persist across consecutive pen events.
        step = max(1.0, self.size * brush['spacing'])
        pressure_factor = 1.0 - brush['pressure_size']/100.0 * (1.0 - pressure)
        diameter = max(1.0, self.size * pressure_factor) if tablet else self.size
        if self.last is None:
            self._paint_custom_stamp(painter, point, diameter, pressure, 0.0)
            self._stamp_distance = 0.0
            return
        dx, dy = point.x() - self.last.x(), point.y() - self.last.y()
        length = math.hypot(dx, dy)
        if length < 0.001:
            return
        direction = math.degrees(math.atan2(dy, dx))
        distance = step - self._stamp_distance
        while distance <= length:
            t = distance / length
            self._paint_custom_stamp(painter, QPointF(self.last.x() + dx*t, self.last.y() + dy*t), diameter, pressure, direction)
            distance += step
        self._stamp_distance = (self._stamp_distance + length) % step

    def stroke(self, point, pressure, tablet):
        if not self.drawing:
            return
        layer = self.layer_by_id(self._stroke_layer_id)
        if layer is None:
            return
        pressure = max(0.0, min(1.0, pressure))
        if self._multi_stroke_before is not None and not getattr(self, '_replaying_multi_stroke', False):
            self._multi_stroke_samples.append((QPointF(point), pressure, tablet))
        width = self.size * (0.15 + 0.85 * pressure) if tablet else self.size
        self._include_point(point, width)
        if self.last is not None:
            self._include_point(self.last, self.size)
        painter = QPainter(layer.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.selection_path is not None:
            painter.setClipPath(self.selection_path)
        elif self.selection is not None:
            painter.setClipRect(self.selection)
        if self.tool == 'eraser':
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.setPen(QPen(QColor(0, 0, 0, 255), width, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            if self.last is None: painter.drawPoint(point)
            else: painter.drawLine(self.last, point)
        elif self.active_custom_brush in self.custom_brushes:
            # Include the entire stamp footprint in the undo patch.
            self._include_point(point, self.size * (1 + self.custom_brushes[self.active_custom_brush]['scatter']/100.0) * 2 + 8)
            if self.last is not None: self._include_point(self.last, self.size * (1 + self.custom_brushes[self.active_custom_brush]['scatter']/100.0) * 2 + 8)
            self._stroke_custom(painter, point, width, pressure, tablet)
        else:
            preset = self.brush_preset
            opacity = self.brush_settings[preset]['opacity'] / 100.0
            if preset == 'Airbrush':
                # A soft radial alpha stamp, spaced along the line for smooth movement.
                dx = point.x() - self.last.x() if self.last is not None else 0.0
                dy = point.y() - self.last.y() if self.last is not None else 0.0
                steps = max(1, math.ceil(math.hypot(dx, dy) / max(2.0, width * 0.20)))
                for i in range(steps + 1):
                    t = i / steps
                    x = (self.last.x() + dx * t) if self.last is not None else point.x()
                    y = (self.last.y() + dy * t) if self.last is not None else point.y()
                    r = max(1.0, width / 2.0)
                    grad = QRadialGradient(QPointF(x, y), r)
                    center = QColor(self.color); center.setAlphaF(min(1.0, opacity * 0.24))
                    edge = QColor(self.color); edge.setAlpha(0)
                    grad.setColorAt(0.0, center); grad.setColorAt(1.0, edge)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(grad)
                    painter.drawEllipse(QPointF(x, y), r, r)
            else:
                ink_width = max(0.75, width * (0.75 if preset == 'Ink' else 1.0))
                color = QColor(self.color)
                # Pencil is semi-transparent, with subtle tapered pressure response.
                color.setAlphaF(min(1.0, opacity * (0.50 if preset == 'Pencil' else 1.0)))
                painter.setPen(QPen(color, ink_width, Qt.PenStyle.SolidLine,
                                    Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                if self.last is None: painter.drawPoint(point)
                else: painter.drawLine(self.last, point)
        painter.end()
        self.last = QPointF(point)
        self.update()

    def _end_stroke(self):
        if not self.drawing:
            return
        layer = self.layer_by_id(self._stroke_layer_id)
        if layer is not None and self._multi_stroke_before is not None:
            before_snapshot = self._multi_stroke_before
            samples = list(self._multi_stroke_samples)
            seen = {(layer.id, layer.cel_id)}
            original_id = self._stroke_layer_id
            original_last = self.last
            original_bounds = self._stroke_bounds
            self._replaying_multi_stroke = True
            try:
                for index in sorted(set(getattr(self, 'multi_edit_frames', []))):
                    if not 0 <= index < len(self.frames) or index == self._stroke_frame:
                        continue
                    target = next((item for item in self.frames[index] if item.id == original_id), None)
                    if target is None or target.mode != 'animated' or not target.visible:
                        continue
                    key = (target.id, target.cel_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    self._stroke_layer_id = target.id
                    # layer_by_id normally resolves the current frame, so replay against
                    # the target via a temporary frame switch with no playhead signal.
                    saved_layers = self.layers
                    self.layers = self.frames[index]
                    self.last = None
                    self._stamp_distance = 0.0
                    self._stroke_bounds = QRectF()
                    try:
                        for sample_point, sample_pressure, sample_tablet in samples:
                            self.stroke(sample_point, sample_pressure, sample_tablet)
                    finally:
                        self.layers = saved_layers
                after_snapshot = self._timeline_snapshot()
                self._push(dict(type='timeline_snapshot', before=before_snapshot, after=after_snapshot))
            finally:
                self._replaying_multi_stroke = False
                self._stroke_layer_id = original_id
                self.last = original_last
                self._stroke_bounds = original_bounds
        elif layer is not None and self._before_stroke is not None and not self._stroke_bounds.isNull():
            rect = self._stroke_bounds.toAlignedRect().intersected(layer.image.rect())
            if not rect.isEmpty():
                before = self._before_stroke.copy(rect)
                after = layer.image.copy(rect)
                if before != after:
                    self._push(dict(type='patch', id=layer.id, frame=self._stroke_frame, rect=rect,
                                    before=before, after=after))
        self.drawing = False
        self.input_kind = None
        self.last = None
        self._before_stroke = None
        self._stroke_bounds = None
        self._stroke_layer_id = None
        self.frames_changed.emit()

    def _apply(self, cmd, forward):
        typ = cmd['type']
        if typ == 'patch':
            frame = cmd.get('frame', self.frame_index)
            if not 0 <= frame < len(self.frames):
                return
            layer = next((x for x in self.frames[frame] if x.id == cmd['id']), None)
            if layer is None:
                return
            p = QPainter(layer.image)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            p.drawImage(cmd['rect'].topLeft(), cmd['after'] if forward else cmd['before'])
            p.end()
        elif typ in ('add', 'remove'):
            insert = (typ == 'add') == forward
            for frame in self.frames:
                if insert:
                    original = cmd['layer']
                    image = original.image if original.mode == 'static' else (original.image if frame is self.layers else transparent_image(self.width_px, self.height_px))
                    frame.insert(min(cmd['index'], len(frame)), Layer(original.id, original.name, image, original.visible, original.opacity, original.mode))
                else:
                    frame[:] = [x for x in frame if x.id != cmd['layer'].id]
            self.active_id = cmd['layer'].id if insert else cmd['previous_active']
        elif typ == 'property':
            for frame in self.frames:
                layer = next((x for x in frame if x.id == cmd['id']), None)
                if layer:
                    setattr(layer, cmd['field'], cmd['after'] if forward else cmd['before'])
        elif typ == 'move':
            for frame in self.frames:
                layer = next((x for x in frame if x.id == cmd['id']), None)
                if layer:
                    frame.remove(layer)
                    frame.insert(cmd['after'] if forward else cmd['before'], layer)
        elif typ == 'motion_key':
            obj = next((x for x in self.motion_objects if x.id == cmd['id']), None)
            if obj is not None:
                value = cmd['after'] if forward else cmd['before']
                if value is None:
                    obj.keys.pop(cmd['frame'], None)
                else:
                    obj.keys[cmd['frame']] = tuple(value)
                self.motion_changed.emit()
        elif typ == 'timeline_snapshot':
            self._restore_timeline_snapshot(cmd['after'] if forward else cmd['before'])
        elif typ in ('frame_add', 'frame_delete'):
            # Retain the exact removed/inserted cel objects, including static-layer
            # sharing. A command stores before/after key maps for every motion object.
            inserting = (typ == 'frame_add') == forward
            if inserting:
                self.frames.insert(cmd['index'], cmd['layers'])
            else:
                removed = self.frames.pop(cmd['index'])
                if removed is not cmd['layers']:
                    raise RuntimeError('Timeline history is out of sync')
            target = cmd['after_frame'] if forward else cmd['before_frame']
            self.frame_index = min(target, len(self.frames) - 1)
            for obj in self.motion_objects:
                if obj.id in cmd['keys_before']:
                    src = cmd['keys_after'] if forward else cmd['keys_before']
                    obj.keys = dict(src[obj.id])
            self.active_id = cmd['active_id']
            self.selection = None
            self.drag_rect = None
            self.move_preview = None
            self.motion_changed.emit()
            self.playhead_changed.emit(self.frame_index)
        self.layers = self.frames[self.frame_index]
        self.document_changed.emit()
        self.update()
        self._mark_dirty()
        self.frames_changed.emit()

    def undo(self):
        if self.drawing or not self._undo:
            return
        cmd = self._undo.pop()
        self._apply(cmd, False)
        if cmd['type'] == 'patch' and cmd.get('frame') is not None:
            self.change_frame(cmd['frame'])
        self._redo.append(cmd)
        self.history_changed.emit(bool(self._undo), bool(self._redo))

    def redo(self):
        if self.drawing or not self._redo:
            return
        cmd = self._redo.pop()
        self._apply(cmd, True)
        if cmd['type'] == 'patch' and cmd.get('frame') is not None:
            self.change_frame(cmd['frame'])
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

    def set_opacity(self, value):
        layer = self.active_layer()
        if layer is None or layer.opacity == value or self.drawing:
            return
        value = max(0, min(100, int(value)))
        cmd = dict(type='property', id=layer.id, field='opacity',
                   before=layer.opacity, after=value)
        self._apply(cmd, True)
        self._push(cmd)

    def change_tool(self, tool):
        if self.drawing or self.drag_origin is not None:
            return
        self.tool = tool
        self.eraser = tool == "eraser"
        self.refresh_cursor()

    def set_selection_mode(self, mode):
        if mode not in ('rectangle', 'freehand', 'polygonal'):
            return
        self.selection_mode = mode
        self.lasso_points = []
        self.lasso_preview = None
        self._polygon_last_click = None
        self.drag_rect = None
        self.drag_origin = None
        self.update()

    def set_selection_path(self, path):
        self.lasso_points = []
        self.lasso_preview = None
        self._polygon_last_click = None
        if path is None or path.isEmpty():
            self.selection = None
            self.selection_path = None
            self.selection_mask = None
        else:
            bounds = path.boundingRect().toAlignedRect().intersected(QRect(0, 0, self.width_px, self.height_px))
            if bounds.isEmpty():
                self.selection = self.selection_path = self.selection_mask = None
            else:
                self.selection = bounds
                self.selection_path = QPainterPath(path)
                mask = transparent_image(self.width_px, self.height_px)
                painter = QPainter(mask)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.fillPath(path, QColor(255, 255, 255, 255))
                painter.end()
                self.selection_mask = mask
        self.update()

    def set_selection(self, rect):
        if rect is None or rect.isEmpty():
            self.set_selection_path(None)
        else:
            path = QPainterPath()
            path.addRect(QRectF(rect.intersected(QRect(0, 0, self.width_px, self.height_px))))
            self.set_selection_path(path)

    def _masked_crop(self, image, rect, mask=None):
        crop = image.copy(rect)
        actual_mask = self.selection_mask if mask is None else mask
        if actual_mask is not None:
            painter = QPainter(crop)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            painter.drawImage(QPoint(-rect.x(), -rect.y()), actual_mask)
            painter.end()
        return crop

    def _clear_selected(self, painter, rect):
        if self.selection_mask is None:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
        else:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            painter.drawImage(0, 0, self.selection_mask)

    def _update_lasso_preview(self, position=None):
        if not self.lasso_points:
            self.lasso_preview = None
            return
        path = QPainterPath(self.lasso_points[0])
        for point in self.lasso_points[1:]:
            path.lineTo(point)
        if position is not None and self.selection_mode == 'polygonal':
            path.lineTo(position)
        self.lasso_preview = path
        self.update()

    def finish_polygon(self):
        if self.selection_mode != 'polygonal' or len(self.lasso_points) < 3:
            return
        path = QPainterPath(self.lasso_points[0])
        for point in self.lasso_points[1:]:
            path.lineTo(point)
        path.closeSubpath()
        self.set_selection_path(path)

    def select_all(self):
        self.set_selection(QRect(0, 0, self.width_px, self.height_px))

    def deselect(self):
        self.set_selection(None)

    def keyPressEvent(self, event):
        if self.tool == 'select' and self.selection_mode == 'polygonal' and self.lasso_points:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.finish_polygon(); event.accept(); return
            if event.key() == Qt.Key.Key_Backspace:
                self.lasso_points.pop(); self._update_lasso_preview(); event.accept(); return
            if event.key() == Qt.Key.Key_Escape:
                self.lasso_points.clear(); self.lasso_preview = None; self.update(); event.accept(); return
        if self.transform_session is not None:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.apply_transform(keep_selection=bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
                event.accept()
                return
            if event.key() == Qt.Key.Key_Escape:
                self.cancel_transform()
                event.accept()
                return
        super().keyPressEvent(event)

    def _point(self, position):
        return QPoint(max(0, min(self.width_px-1, int(position.x()))),
                      max(0, min(self.height_px-1, int(position.y()))))

    def _start_interaction(self, position):
        if self.playing:
            return
        point = self._point(position)
        if self.tool == 'transform':
            self._transform_press(QPointF(position))
        elif self.tool == 'select':
            if self.selection_mode == 'polygonal':
                pos = QPointF(position)
                now = time.monotonic()
                double_tap = (self._polygon_last_click is not None
                              and now - self._polygon_last_click[0] < 0.38
                              and (pos - self._polygon_last_click[1]).manhattanLength() <= 9 / self.zoom)
                self._polygon_last_click = (now, pos)
                if len(self.lasso_points) >= 3 and (
                        (pos - self.lasso_points[0]).manhattanLength() <= 12 / self.zoom or double_tap):
                    self.finish_polygon()
                elif not double_tap:
                    self.lasso_points.append(pos)
                    self._update_lasso_preview(pos)
                return
            self.drag_origin = point
            if self.selection_mode == 'freehand':
                self.lasso_points = [QPointF(position)]
                self._update_lasso_preview()
            else:
                self.drag_rect = QRect(point, point).normalized()
                self.update()
        elif self.tool == 'move':
            layer = self.active_layer()
            if layer is None or not layer.visible:
                self.diagnostic.emit('Select a visible layer to move.')
                return
            self.drag_origin = point
            self.move_layer_id = layer.id
            self.move_source_rect = self.selection or layer.image.rect()
            self.move_source = self._masked_crop(layer.image, self.move_source_rect)
            self.move_preview = QRect(self.move_source_rect)
            self.move_offset = QPoint(0, 0)
            self.update()

    def _update_interaction(self, position):
        if self.tool == 'transform' and self.transform_drag is not None:
            self._transform_move(QPointF(position))
            return
        if self.tool == 'select' and self.selection_mode == 'polygonal':
            self._update_lasso_preview(QPointF(position))
            return
        if self.drag_origin is None:
            return
        point = self._point(position)
        if self.tool == 'select':
            if self.selection_mode == 'freehand':
                pos = QPointF(position)
                if not self.lasso_points or (pos - self.lasso_points[-1]).manhattanLength() >= 0.5:
                    self.lasso_points.append(pos)
                self._update_lasso_preview()
            else:
                self.drag_rect = QRect(self.drag_origin, point).normalized().adjusted(0, 0, 1, 1)
        elif self.tool == 'move' and self.move_preview is not None:
            self.move_offset = point - self.drag_origin
            self.move_preview = self.move_source_rect.translated(self.move_offset)
        self.update()

    def _finish_interaction(self, position):
        if self.tool == 'transform' and self.transform_drag is not None:
            self._transform_move(QPointF(position))
            self.transform_drag = None
            return
        if self.drag_origin is None:
            return
        self._update_interaction(position)
        if self.tool == 'select':
            if self.selection_mode == 'freehand':
                if len(self.lasso_points) >= 3:
                    path = QPainterPath(self.lasso_points[0])
                    for vertex in self.lasso_points[1:]: path.lineTo(vertex)
                    path.closeSubpath()
                    self.set_selection_path(path)
                self.lasso_points = []
                self.lasso_preview = None
            else:
                self.set_selection(self.drag_rect)
                self.drag_rect = None
        elif self.tool == 'move' and self.move_source is not None:
            layer = self.layer_by_id(self.move_layer_id)
            if layer is not None and not self.move_offset.isNull():
                source = self.move_source_rect
                destination = source.translated(self.move_offset)
                affected = source.united(destination).intersected(layer.image.rect())
                before = layer.image.copy(affected)
                painter = QPainter(layer.image)
                self._clear_selected(painter, source)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                painter.drawImage(destination.topLeft(), self.move_source)
                painter.end()
                after = layer.image.copy(affected)
                if before != after:
                    self._push(dict(type='patch', id=layer.id, rect=affected,
                                    before=before, after=after))
                if self.selection_path is not None:
                    self.set_selection_path(self.selection_path.translated(self.move_offset))
            self.move_preview = None
            self.move_source = None
            self.move_layer_id = None
        self.drag_origin = None
        self.update()

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
        for frame in self.frames:
            for peer in frame:
                if peer.id == layer.id and peer.cel_id == layer.cel_id:
                    peer.image = after
        self._push(dict(type='patch', id=layer.id, rect=layer.image.rect(), before=before, after=after.copy()))
        self.update()
        self.frames_changed.emit()

    def tabletEvent(self, event):
        typ = event.type()
        pressure = float(event.pressure())
        self.setFocus(Qt.FocusReason.MouseFocusReason) if typ == QEvent.Type.TabletPress else None
        self.show_hover(event.position() / self.zoom, pressure if self.drawing else 1.0)
        device = event.pointingDevice()
        name = device.name() if device else 'Unknown tablet'
        if self.playing:
            event.accept()
            return
        if typ == QEvent.Type.TabletPress:
            self.ignore_mouse = True
            if self.tool in ("brush", "eraser"):
                self._begin_stroke('tablet')
                self.stroke(event.position() / self.zoom, pressure, True)
            else:
                self._start_interaction(event.position() / self.zoom)
        elif typ == QEvent.Type.TabletMove:
            if self.drawing and self.input_kind == 'tablet':
                self.stroke(event.position() / self.zoom, pressure, True)
            elif self.drag_origin is not None or self.transform_drag is not None:
                self._update_interaction(event.position() / self.zoom)
        elif typ == QEvent.Type.TabletRelease:
            if self.drawing and self.input_kind == 'tablet':
                self.stroke(event.position() / self.zoom, pressure, True)
                self._end_stroke()
            if self.drag_origin is not None or self.transform_drag is not None:
                self._finish_interaction(event.position() / self.zoom)
            self.ignore_mouse = False
        self.diagnostic.emit(f'TABLET: {name} | pressure: {pressure:.3f} | tilt: '
                             f'{event.xTilt():.0f}, {event.yTilt():.0f} | {typ.name}')
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if self.tool == 'select' and self.selection_mode == 'polygonal':
            self.finish_polygon()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if self.playing:
            event.accept()
            return
        self.show_hover(event.position() / self.zoom, 1.0)
        if not self.ignore_mouse and event.button() == Qt.MouseButton.LeftButton:
            if self.tool in ('brush', 'eraser'):
                self._begin_stroke('mouse')
                self.stroke(event.position() / self.zoom, 1.0, False)
            else:
                self._start_interaction(event.position() / self.zoom)
            self.diagnostic.emit('MOUSE input (fixed width; no pressure)')
        event.accept()

    def mouseMoveEvent(self, event):
        if not self.ignore_mouse:
            self.show_hover(event.position() / self.zoom, 1.0)
        if (not self.ignore_mouse and self.drawing and self.input_kind == 'mouse'
                and event.buttons() & Qt.MouseButton.LeftButton):
            self.stroke(event.position() / self.zoom, 1.0, False)
        elif (self.drag_origin is not None or self.transform_drag is not None) and event.buttons() & Qt.MouseButton.LeftButton:
            self._update_interaction(event.position() / self.zoom)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.input_kind == 'mouse':
                self._end_stroke()
            if self.drag_origin is not None or self.transform_drag is not None:
                self._finish_interaction(event.position() / self.zoom)
        event.accept()

    def _copy_layers(self, layers, duplicate=True):
        return [Layer(x.id, x.name,
                      x.image if x.mode == 'static' else (x.image.copy() if duplicate else transparent_image(self.width_px, self.height_px)),
                      x.visible, x.opacity, x.mode, x.cel_id if x.mode == 'static' else uuid.uuid4().hex) for x in layers]

    def set_layer_mode(self, mode):
        """Switch the active track between shared static art and independent cels."""
        if mode not in ('static', 'animated') or self.drawing or self.playing:
            return
        target = self.active_layer()
        if target is None or target.mode == mode:
            return
        # Static -> animated keeps the visible art in each cel and detaches it.
        # Animated -> static deliberately chooses the *current* cel for all frames.
        shared = target.image.copy()
        shared_id = uuid.uuid4().hex
        for frame in self.frames:
            layer = next(x for x in frame if x.id == target.id)
            layer.mode = mode
            layer.image = shared if mode == 'static' else shared.copy() if frame is self.frames[self.frame_index] else layer.image.copy()
            layer.cel_id = shared_id if mode == 'static' else uuid.uuid4().hex
        self._undo.clear()
        self._redo.clear()
        self.history_changed.emit(False, False)
        self._notify_layers()

    def _synchronize_tracks(self):
        """All frames have identical layer IDs/order/metadata; static images share identity."""
        template = self.layers
        for frame in self.frames:
            previous = {layer.id: layer for layer in frame}
            result = []
            for track in template:
                old = previous.get(track.id)
                image = (track.image if track.mode == 'static' else
                         old.image if old is not None else transparent_image(self.width_px, self.height_px))
                result.append(Layer(track.id, track.name, image, track.visible, track.opacity, track.mode, old.cel_id if old is not None else uuid.uuid4().hex))
            frame[:] = result
        self.layers = self.frames[self.frame_index]


    def _timeline_snapshot(self):
        """Copy frame data, preserving shared-image identity within each cel group."""
        image_cache = {}
        snapshot = []
        for frame_layers in self.frames:
            row = []
            for layer in frame_layers:
                key = (layer.id, layer.cel_id) if layer.mode != 'static' else (layer.id, 'static')
                if key not in image_cache:
                    image_cache[key] = layer.image.copy()
                row.append(Layer(layer.id, layer.name, image_cache[key], layer.visible,
                                 layer.opacity, layer.mode, layer.cel_id))
            snapshot.append(row)
        return snapshot

    def _restore_timeline_snapshot(self, snapshot):
        self.frames = self._clone_snapshot(snapshot)
        self.frame_index = min(self.frame_index, len(self.frames) - 1)
        self.layers = self.frames[self.frame_index]
        self.deselect()

    def _clone_snapshot(self, snapshot):
        cache = {}
        result = []
        for frame_layers in snapshot:
            row = []
            for layer in frame_layers:
                key = (layer.id, layer.cel_id) if layer.mode != 'static' else (layer.id, 'static')
                if key not in cache:
                    cache[key] = layer.image.copy()
                row.append(Layer(layer.id, layer.name, cache[key], layer.visible,
                                 layer.opacity, layer.mode, layer.cel_id))
            result.append(row)
        return result

    def _edit_timeline(self, operation):
        if self.playing or self.drawing or self.transform_session is not None:
            return False
        before = self._timeline_snapshot()
        try:
            result = operation()
        except Exception:
            self._restore_timeline_snapshot(before)
            raise
        if result is False:
            return False
        self.layers = self.frames[self.frame_index]
        after = self._timeline_snapshot()
        self._push(dict(type='timeline_snapshot', before=before, after=after))
        self.document_changed.emit()
        return True

    def hold_cel(self, duration):
        """Extend current cel into subsequent blank frames, without overwriting art."""
        duration = max(1, int(duration))
        source_index = self.frame_index
        source = self.active_layer()
        if source is None or source.mode != 'animated':
            return False
        target_end = min(120, source_index + duration)
        # Never silently destroy independent artwork.
        for index in range(source_index + 1, min(target_end, len(self.frames))):
            target = next(x for x in self.frames[index] if x.id == source.id)
            if target.cel_id != source.cel_id and not target.image.isNull() and self._has_pixels(target.image):
                return False
        def operation():
            while len(self.frames) < target_end:
                self.frames.append(self._copy_layers(self.frames[-1], duplicate=False))
            for index in range(source_index + 1, target_end):
                target = next(x for x in self.frames[index] if x.id == source.id)
                target.image = source.image
                target.cel_id = source.cel_id
        return self._edit_timeline(operation)

    @staticmethod
    def _has_pixels(image):
        """Quick alpha test, including fully transparent black images."""
        alpha = image.convertToFormat(QImage.Format.Format_Alpha8)
        data = bytes(alpha.constBits())
        return data.count(0) != len(data)

    def link_cel(self, source_index):
        """Reuse a cel at current playhead, keeping its source alive elsewhere."""
        target = self.active_layer()
        if target is None or target.mode != 'animated' or not 0 <= source_index < len(self.frames):
            return False
        source = next(x for x in self.frames[source_index] if x.id == target.id)
        if target.cel_id == source.cel_id:
            return False
        def operation():
            target.image = source.image
            target.cel_id = source.cel_id
        return self._edit_timeline(operation)

    def unlink_cel(self):
        target = self.active_layer()
        if target is None or target.mode != 'animated':
            return False
        if sum(1 for f in self.frames for x in f if x.id == target.id and x.cel_id == target.cel_id) < 2:
            return False
        def operation():
            target.image = target.image.copy()
            target.cel_id = uuid.uuid4().hex
        return self._edit_timeline(operation)

    def split_hold(self):
        """Make the current exposure independent (a new editable key cel)."""
        target = self.active_layer()
        if target is None or target.mode != 'animated':
            return False
        def operation():
            target.image = target.image.copy()
            target.cel_id = uuid.uuid4().hex
        return self._edit_timeline(operation)

    def cel_kind(self, layer_id, index):
        layer = next((x for x in self.frames[index] if x.id == layer_id), None)
        if layer is None:
            return 'empty'
        if layer.mode == 'static':
            return 'static'
        peers = [j for j, f in enumerate(self.frames)
                 if next(x for x in f if x.id == layer_id).cel_id == layer.cel_id]
        if peers and peers[0] != index:
            return 'hold' if index - 1 in peers else 'link'
        return 'key' if self._has_pixels(layer.image) else 'empty'

    def _finish_frame_change(self, mark_dirty=True):
        self.deselect()
        self.document_changed.emit()
        if mark_dirty:
            self.frames_changed.emit()
            self._mark_dirty()
        else:
            self.playhead_changed.emit(self.frame_index)
        self.update()

    def change_frame(self, index, playback=False):
        if self.transform_session is not None:
            self.cancel_transform()
        if self.drawing or self.drag_origin is not None or not 0 <= index < len(self.frames):
            return
        if index == self.frame_index:
            return
        self.frame_index = index
        self.layers = self.frames[index]
        self.active_id = self.active_id if self.layer_by_id(self.active_id) else self.layers[-1].id
        self._finish_frame_change(mark_dirty=False)
        self.motion_changed.emit()

    def _motion_key_snapshot(self):
        return {obj.id: dict(obj.keys) for obj in self.motion_objects}

    def add_frame(self, duplicate=False):
        if self.drawing or self.drag_origin is not None or self.playing or len(self.frames) >= 120:
            return
        before = self._motion_key_snapshot()
        index = self.frame_index + 1
        layers = self._copy_layers(self.layers, duplicate=duplicate)
        after = {oid: {k + 1 if k >= index else k: v for k, v in keys.items()}
                 for oid, keys in before.items()}
        cmd = dict(type='frame_add', index=index, layers=layers,
                   before_frame=self.frame_index, after_frame=index,
                   active_id=self.active_id, keys_before=before, keys_after=after)
        self._apply(cmd, True)
        self._push(cmd)

    def delete_frame(self):
        if self.drawing or self.drag_origin is not None or self.playing or len(self.frames) <= 1:
            return
        removed = self.frame_index
        before = self._motion_key_snapshot()
        after = {}
        for oid, keys in before.items():
            shifted = {k - 1 if k > removed else k: v for k, v in keys.items() if k != removed}
            after[oid] = shifted if shifted else {0: (0.0, 0.0, 100.0, 0.0)}
        cmd = dict(type='frame_delete', index=removed, layers=self.frames[removed],
                   before_frame=removed, after_frame=min(removed, len(self.frames) - 2),
                   active_id=self.active_id, keys_before=before, keys_after=after)
        self._apply(cmd, True)
        self._push(cmd)

    def frame_thumbnail(self, index):
        result = QImage(self.width_px, self.height_px, IMAGE_FORMAT)
        result.fill(Qt.GlobalColor.white)
        p = QPainter(result)
        for layer in self.frames[index]:
            if layer.visible:
                p.setOpacity(layer.opacity / 100.0)
                p.drawImage(0, 0, layer.image)
        self.draw_motion_objects(p, index)
        p.end()
        return result.scaled(90, 60, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)

    def render_frame(self, index, background=None):
        """Render a specific frame without changing the current frame or editor overlays."""
        image = QImage(self.width_px, self.height_px, IMAGE_FORMAT)
        image.fill(QColor(background) if background else Qt.GlobalColor.transparent)
        painter = QPainter(image)
        for layer in self.frames[index]:
            if layer.visible:
                painter.setOpacity(layer.opacity / 100.0)
                painter.drawImage(0, 0, layer.image)
                painter.setOpacity(1.0)
        self.draw_motion_objects(painter, index)
        painter.end()
        return image

    def reset_document(self, width=WIDTH, height=HEIGHT):
        self.color = QColor('#000000')
        self.cancel_transform()
        self.drawing = False
        self.drag_origin = None
        self.drag_rect = None
        self.move_source = None
        self.move_preview = None
        self.selection = None
        self.selection_path = None
        self.selection_mask = None
        self.lasso_points = []
        self.lasso_preview = None
        self.width_px, self.height_px = width, height
        self.layers = [Layer(uuid.uuid4().hex, 'Layer 1', transparent_image(width, height))]
        self.frames = [self.layers]
        self.motion_objects = []
        self.active_motion_id = None
        self.motion_changed.emit()
        self.active_id = self.layers[0].id
        self.frame_index = 0
        self.fps = 12
        self.onion_enabled = False
        self.onion_opacity = 35
        self.onion_previous = 1
        self.onion_next = 1
        self.loop_playback = True
        self.audio_bytes = None
        self.audio_name = ''
        self.audio_suffix = ''
        self._undo.clear()
        self._redo.clear()
        self.setFixedSize(round(width * self.zoom), round(height * self.zoom))
        self.dirty = False
        self.history_changed.emit(False, False)
        self.dirty_changed.emit()
        self.document_changed.emit()
        self.frames_changed.emit()
        self.update()

    def save_project(self, path):
        # A frame owns its layer images; each frame has independent editable pixels.
        manifest = dict(format='linux-animation-studio', version=PROJECT_VERSION,
                        width=self.width_px, height=self.height_px,
                        active_frame=self.frame_index, fps=self.fps,
                        onion_enabled=self.onion_enabled, onion_opacity=self.onion_opacity,
                        onion_previous=self.onion_previous, onion_next=self.onion_next,
                        loop_playback=getattr(self, 'loop_playback', True), brush_color=self.color.name(), frames=[], motion_objects=[],
                        audio=None)
        path = Path(path)
        temporary = path.with_name(path.name + '.tmp')
        try:
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for index, layers in enumerate(self.frames):
                    records = []
                    for layer in layers:
                        filename = f'frames/{index}/{layer.id}.png'
                        records.append(dict(id=layer.id, name=layer.name, visible=layer.visible,
                                            opacity=layer.opacity, mode=layer.mode, cel_id=layer.cel_id, file=filename))
                        archive.writestr(filename, png_bytes(layer.image))
                    manifest['frames'].append(dict(layers=records))
                for obj in self.motion_objects:
                    filename = f'motion/{obj.id}.png'
                    archive.writestr(filename, png_bytes(obj.image))
                    manifest['motion_objects'].append(dict(id=obj.id, name=obj.name, file=filename,
                        keys={str(k): list(v) for k, v in obj.keys.items()}))
                manifest['active_motion_id'] = self.active_motion_id
                manifest['active_layer'] = self.active_id
                if getattr(self, 'audio_bytes', None):
                    suffix = self.audio_suffix
                    if suffix not in ('.wav', '.mp3'):
                        raise ValueError('Unsupported embedded audio extension')
                    audio_path = 'audio/track' + suffix
                    archive.writestr(audio_path, self.audio_bytes)
                    manifest['audio'] = {'file': audio_path, 'name': self.audio_name}
                archive.writestr('manifest.json', json.dumps(manifest, indent=2))
                archive.writestr('preview.png', png_bytes(self.composite(True)))
            temporary.replace(path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        self.dirty = False
        self.dirty_changed.emit()

    def load_project(self, path):
        # Validate entire archive before replacing the current document.
        with zipfile.ZipFile(path, 'r') as archive:
            info = json.loads(archive.read('manifest.json'))
            version = info.get('version')
            if info.get('format') != 'linux-animation-studio' or version not in (1, 2, 3, 4, 5, 6):
                raise ValueError('Unsupported .las project format/version')
            width, height = int(info['width']), int(info['height'])
            if not (1 <= width <= 8192 and 1 <= height <= 8192):
                raise ValueError('Invalid canvas dimensions')
            frame_entries = [dict(layers=info['layers'])] if version == 1 else info['frames']
            if not isinstance(frame_entries, list) or not 1 <= len(frame_entries) <= 120:
                raise ValueError('Invalid frame list')
            frames = []
            for index, frame in enumerate(frame_entries):
                entries = frame['layers']
                if not isinstance(entries, list) or not 1 <= len(entries) <= 100:
                    raise ValueError('Invalid layer list')
                layers = []
                seen = set()
                for entry in entries:
                    lid = entry['id']
                    if not isinstance(lid, str) or not lid.isalnum() or lid in seen:
                        raise ValueError('Invalid or duplicate layer ID')
                    seen.add(lid)
                    filename = (f'layers/{lid}.png' if version == 1 else
                                f'frames/{index}/{lid}.png')
                    if entry['file'] != filename:
                        raise ValueError('Invalid layer asset path')
                    image = image_from_bytes(archive.read(filename), width, height)
                    opacity = int(entry.get('opacity', 100))
                    if not 0 <= opacity <= 100:
                        raise ValueError('Invalid layer opacity')
                    layers.append(Layer(lid, str(entry['name']), image,
                                        bool(entry['visible']), opacity, entry.get('mode', 'animated') if version >= 4 else 'animated',
                                        entry.get('cel_id', uuid.uuid4().hex) if version >= 5 else uuid.uuid4().hex))
                frames.append(layers)
            # Older projects can contain independently created layers per frame.
            # Promote every unique ID to its own persistent track, preserving art.
            # If IDs match across frames, the matching artwork becomes that track's cel.
            definitions = []
            observed = set()
            for frame in frames:
                for layer in frame:
                    if layer.id not in observed:
                        observed.add(layer.id)
                        definitions.append(layer)
            if len(definitions) > 100:
                raise ValueError('Too many layer tracks after migration (maximum 100)')
            aligned = []
            for frame in frames:
                lookup = {layer.id: layer for layer in frame}
                aligned.append([Layer(template.id, template.name,
                    lookup[template.id].image if template.id in lookup else transparent_image(width, height),
                    template.visible, template.opacity, template.mode,
                    lookup[template.id].cel_id if template.id in lookup else uuid.uuid4().hex) for template in definitions])
            frames = aligned
            for track_index, template in enumerate(definitions):
                if template.mode == 'static':
                    shared = frames[0][track_index].image
                    for frame in frames:
                        frame[track_index].image = shared
            if version >= 5:
                shared_cels = {}
                for row in frames:
                    for layer in row:
                        if not isinstance(layer.cel_id, str) or len(layer.cel_id) != 32 or not all(c in '0123456789abcdef' for c in layer.cel_id):
                            raise ValueError('Invalid cel identifier')
                        key = (layer.id, layer.cel_id)
                        if key in shared_cels:
                            layer.image = shared_cels[key]
                        else:
                            shared_cels[key] = layer.image
            index = int(info.get('active_frame', 0)) if version >= 2 else 0
            if not 0 <= index < len(frames):
                raise ValueError('Invalid active frame')
            fps = int(info.get('fps', 12)) if version >= 2 else 12
            if not 1 <= fps <= 60:
                raise ValueError('Invalid FPS')
            motion_objects = []
            if version >= 3:
                for rec in info.get('motion_objects', []):
                    oid = rec['id']
                    if not isinstance(oid, str) or not oid.isalnum():
                        raise ValueError('Invalid motion object ID')
                    filename = f'motion/{oid}.png'
                    if rec.get('file') != filename:
                        raise ValueError('Invalid motion asset path')
                    keys = {}
                    for key, values in rec['keys'].items():
                        frame_number = int(key)
                        values = tuple(float(v) for v in values)
                        if not (0 <= frame_number < len(frames) and len(values) == 4 and
                                all(math.isfinite(v) for v in values) and 1 <= values[2] <= 400):
                            raise ValueError('Invalid keyframe')
                        keys[frame_number] = values
                    if not keys:
                        raise ValueError('Motion objects need at least one keyframe')
                    motion_objects.append(MotionObject(oid, str(rec['name']),
                        image_from_bytes(archive.read(filename), width, height), keys))
                if len(motion_objects) > 20:
                    raise ValueError('Too many motion objects')
            embedded_audio = None
            embedded_name = ''
            embedded_suffix = ''
            if version >= 6 and info.get('audio'):
                record = info['audio']
                audio_file = record['file']
                if audio_file not in ('audio/track.wav', 'audio/track.mp3'):
                    raise ValueError('Invalid audio asset path')
                audio_info = archive.getinfo(audio_file)
                if audio_info.file_size > 80 * 1024 * 1024:
                    raise ValueError('Embedded audio too large')
                embedded_audio = archive.read(audio_file)
                embedded_name = str(record.get('name', 'Audio'))[:160]
                embedded_suffix = Path(audio_file).suffix
            active_id = info.get('active_layer')
            if not any(layer.id == active_id for layer in frames[index]):
                active_id = frames[index][-1].id
        self.deselect()
        stored_color = QColor(str(info.get('brush_color', '#000000')))
        self.color = stored_color if stored_color.isValid() else QColor('#000000')
        self.width_px, self.height_px = width, height
        self.frames = frames
        self.motion_objects = motion_objects
        saved_motion = info.get('active_motion_id')
        self.active_motion_id = (saved_motion if any(o.id == saved_motion for o in motion_objects)
                                 else (motion_objects[-1].id if motion_objects else None))
        self.motion_changed.emit()
        self.frame_index = index
        self.fps = fps
        self.onion_enabled = bool(info.get('onion_enabled', False))
        self.onion_opacity = max(0, min(100, int(info.get('onion_opacity', 35))))
        self.onion_previous = max(0, min(6, int(info.get('onion_previous', 1))))
        self.onion_next = max(0, min(6, int(info.get('onion_next', 1))))
        self.loop_playback = bool(info.get('loop_playback', True))
        self.audio_bytes = embedded_audio
        self.audio_name = embedded_name
        self.audio_suffix = embedded_suffix
        self.layers = frames[index]
        self.active_id = active_id
        self.setFixedSize(round(width * self.zoom), round(height * self.zoom))
        self._undo.clear()
        self._redo.clear()
        self.history_changed.emit(False, False)
        self.dirty = False
        self.dirty_changed.emit()
        self.document_changed.emit()
        self.frames_changed.emit()
        self.update()


class PannableScrollArea(QScrollArea):
    """One pan state machine for tablet and mouse input.

    ARMED: holding Space or the Pan tool is selected.
    DRAGGING: an input device owns the drag until its real release, Space-up
    (temporary pan only), window deactivation, or a new tool selection.
    The filter observes events globally to survive canvas movement beneath
    the pointer, but only acts on events from this window.
    """
    def __init__(self):
        super().__init__()
        self._pan_state = 'idle'
        self._pan_source = None
        self._pan_device = None
        self._last_global = QPointF()
        self._space_down = False
        self._canvas = None
        self._pan_debug = os.environ.get('LAS_PAN_DEBUG', '').lower() in ('1', 'true', 'yes')
        self._pan_samples = 0
        self.on_canvas_zoom = None
        self.viewport().installEventFilter(self)
        QApplication.instance().installEventFilter(self)

    def setWidget(self, widget):
        super().setWidget(widget)
        self._canvas = widget
        widget.installEventFilter(self)
        self._update_mode()

    def _log_pan(self, message):
        if self._pan_debug:
            print('[LAS PAN]', message, flush=True)

    def _is_pan_tool(self):
        return self._canvas is not None and self._canvas.tool == 'pan'

    def _pan_enabled(self):
        return self._space_down or self._is_pan_tool()

    def _set_cursor(self):
        cursor = (Qt.CursorShape.ClosedHandCursor if self._pan_state == 'dragging'
                  else Qt.CursorShape.OpenHandCursor if self._pan_enabled()
                  else Qt.CursorShape.ArrowCursor)
        self.viewport().setCursor(cursor)
        if self._canvas is not None:
            if self._pan_enabled():
                self._canvas.setCursor(cursor)
            else:
                self._canvas.refresh_cursor()

    def _update_mode(self):
        if self._pan_state != 'dragging':
            self._pan_state = 'armed' if self._pan_enabled() else 'idle'
        self._set_cursor()

    def tool_changed(self):
        if self._pan_state == 'dragging' and not self._space_down:
            self._stop_pan('tool_changed')
        self._update_mode()

    def _stop_pan(self, reason):
        if self._pan_state == 'dragging':
            self._log_pan('STOP reason=' + reason + ' source=' + str(self._pan_source)
                          + ' samples=' + str(self._pan_samples))
        self._pan_source = None
        self._pan_device = None
        self._pan_state = 'armed' if self._pan_enabled() else 'idle'
        self._set_cursor()

    def _start_pan(self, event, source):
        self._pan_state = 'dragging'
        self._pan_source = source
        self._pan_device = event.pointingDevice() if source == 'tablet' else None
        self._last_global = QPointF(event.globalPosition())
        self._pan_samples = 0
        self._log_pan('START source=' + source + ' device=' +
                      (self._pan_device.name() if self._pan_device else 'mouse') +
                      ' global=' + str(self._last_global))
        self._set_cursor()

    def _continue_pan(self, event):
        current = QPointF(event.globalPosition())
        delta = current - self._last_global
        self._last_global = current
        h, v = self.horizontalScrollBar(), self.verticalScrollBar()
        before = (h.value(), v.value())
        # Use floating-point input positions and round the requested movement,
        # so subpixel pen movements don't disappear on HiDPI displays.
        h.setValue(round(before[0] - delta.x()))
        v.setValue(round(before[1] - delta.y()))
        self._pan_samples += 1
        if self._pan_debug and (self._pan_samples % 8 == 1 or self._pan_samples <= 2):
            self._log_pan('MOVE source=' + str(self._pan_source) +
                          ' delta=' + str(delta) + ' scroll=' + str(before) +
                          '->' + str((h.value(), v.value())) +
                          ' limits=' + str((h.maximum(), v.maximum())))

    def _wheel_zoom(self, event):
        """Zoom about the pointer; preserve the same canvas pixel under it."""
        if self._canvas is None or not (event.modifiers() & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            return False
        steps = event.angleDelta().y() / 120.0
        if not steps:
            steps = event.pixelDelta().y() / 100.0
        if not steps:
            return False
        before = self._canvas.zoom
        target = max(0.25, min(8.0, before * (1.15 ** steps)))
        if abs(target - before) < 1e-9:
            event.accept()
            return True
        global_point = event.globalPosition().toPoint()
        pointer = self.viewport().mapFromGlobal(global_point)
        # The canvas is centered when smaller than the viewport, so use the
        # actual widget origin instead of assuming it starts at (0, 0).
        canvas_point = (QPointF(pointer) - QPointF(self._canvas.pos())) / before
        self._canvas.set_zoom(target)
        def preserve_anchor():
            if self._canvas is None or abs(self._canvas.zoom - target) > 1e-6:
                return
            # Adjust scrollbars for the shift caused by resizing the canvas.
            image_point = QPoint(round(canvas_point.x() * target),
                                 round(canvas_point.y() * target))
            projected = self._canvas.mapTo(self.viewport(), image_point)
            offset = projected - pointer
            h, v = self.horizontalScrollBar(), self.verticalScrollBar()
            h.setValue(h.value() + offset.x())
            v.setValue(v.value() + offset.y())
        QTimer.singleShot(0, preserve_anchor)
        if self.on_canvas_zoom is not None:
            self.on_canvas_zoom(target)
        event.accept()
        return True

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.Type.Wheel and (obj is self._canvas or obj is self.viewport()):
            if self._wheel_zoom(event):
                return True
        if t in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease) and event.key() == Qt.Key.Key_Space:
            if self.window().isActiveWindow():
                if not event.isAutoRepeat():
                    self._space_down = t == QEvent.Type.KeyPress
                    if t == QEvent.Type.KeyRelease and self._pan_state == 'dragging' and not self._is_pan_tool():
                        self._stop_pan('space_released')
                    self._update_mode()
                return True  # Prevent QPushButton focus from reactivating.
            return False

        if t in (QEvent.Type.ApplicationDeactivate, QEvent.Type.WindowDeactivate):
            if t == QEvent.Type.ApplicationDeactivate or obj is self.window():
                self._space_down = False
                self._stop_pan('window_deactivated')
                self._update_mode()
            return False

        tablet_press = t == QEvent.Type.TabletPress
        tablet_move = t == QEvent.Type.TabletMove
        tablet_release = t == QEvent.Type.TabletRelease
        mouse_press = t == QEvent.Type.MouseButtonPress
        mouse_move = t == QEvent.Type.MouseMove
        mouse_release = t == QEvent.Type.MouseButtonRelease
        if not (tablet_press or tablet_move or tablet_release or mouse_press or mouse_move or mouse_release):
            return False

        # This is an application-wide filter, so never consume events from other windows.
        if isinstance(obj, QWidget) and obj.window() is not self.window():
            return False
        on_canvas = obj is self._canvas or obj is self.viewport()
        if self._pan_state != 'dragging':
            if not on_canvas:
                return False
            is_middle = mouse_press and event.button() == Qt.MouseButton.MiddleButton
            is_left = mouse_press and event.button() == Qt.MouseButton.LeftButton
            if (tablet_press and self._pan_enabled()) or is_middle or (is_left and self._pan_enabled()):
                self._start_pan(event, 'tablet' if tablet_press else 'mouse')
                event.accept()
                return True
            return False

        # Once a tablet drag owns navigation, Qt's synthesized mouse input
        # must not replace its position or end the gesture.
        if self._pan_source == 'tablet':
            if mouse_press or mouse_move or mouse_release:
                event.accept()
                return True
            if event.pointingDevice() != self._pan_device:
                return False
            if tablet_move:
                self._continue_pan(event)
                event.accept()
                return True
            if tablet_release:
                self._stop_pan('tablet_release')
                event.accept()
                return True
            if tablet_press:
                self._log_pan('DUPLICATE tablet_press ignored')
                event.accept()
                return True
        else:
            if tablet_press:
                # On Wayland a tablet press can arrive after a synthesized
                # mouse press. Promote ownership to the actual tablet.
                self._start_pan(event, 'tablet')
                event.accept()
                return True
            if tablet_move or tablet_release:
                return False
            if mouse_move:
                self._continue_pan(event)
                event.accept()
                return True
            if mouse_release:
                self._stop_pan('mouse_release')
                event.accept()
                return True
        return False


def audio_waveform(data, suffix, bins=180):
    """Produce low-cost peak overview using bundled FFmpeg or the WAV reader."""
    try:
        if resolve_ffmpeg():
            result = subprocess.run([resolve_ffmpeg(), '-hide_banner', '-loglevel', 'error',
                '-i', 'pipe:0', '-f', 's16le', '-ac', '1', '-ar', '8000', 'pipe:1'],
                input=data, capture_output=True, timeout=25, check=True)
            raw = result.stdout
            count = len(raw) // 2
            samples = memoryview(raw[:count*2]).cast('h')
            return [max((abs(samples[j]) for j in range(i*count//bins, (i+1)*count//bins)), default=0)/32768
                    for i in range(bins)] if count else []
        if suffix == '.wav':
            with wave.open(io.BytesIO(data)) as w:
                raw = w.readframes(w.getnframes())
                if w.getsampwidth() != 2:
                    return []
                samples = memoryview(raw).cast('h')
                count = len(samples)
                return [max((abs(samples[j]) for j in range(i*count//bins, (i+1)*count//bins)), default=0)/32768
                        for i in range(bins)] if count else []
    except (ValueError, OSError, subprocess.SubprocessError, wave.Error):
        pass
    return []


class AudioWaveform(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.peaks = []
        self.position = 0
        self.setMinimumHeight(42)
        self.setMaximumHeight(58)
        self.setToolTip('Click or drag to scrub the playhead (audio seeking, not audible shuttle)')
        self._scrubbing = False
        self.on_seek = None

    def _seek_at(self, event):
        if self.on_seek:
            self.on_seek(max(0., min(1., event.position().x() / max(1, self.width()))))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._scrubbing = True
            self._seek_at(event)
            event.accept()

    def mouseMoveEvent(self, event):
        if self._scrubbing:
            self._seek_at(event)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._scrubbing:
            self._seek_at(event)
            self._scrubbing = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#253b42'))
        if self.peaks:
            painter.setPen(QPen(QColor('#85cfc8'), 1))
            mid, amp = self.height() / 2, self.height() * .44
            for i, peak in enumerate(self.peaks):
                x = round(i * (self.width() - 1) / max(1, len(self.peaks) - 1))
                height = max(1, peak * amp)
                painter.drawLine(QPointF(x, mid-height), QPointF(x, mid+height))
        painter.setPen(QPen(QColor('#f4bc66'), 2))
        x = round(self.position * max(1, self.width() - 1))
        painter.drawLine(x, 0, x, self.height())
        painter.end()


class ExposureFrameList(QListWidget):
    """Frame strip with conspicuous drag grips on thumbnail right edges.

    Click the colored grip and drag it onto a later thumbnail to extend
    an exposure. Normal clicks and modifier selections remain native Qt.
    """
    GRIP_WIDTH = 19

    def __init__(self, parent=None):
        super().__init__(parent)
        self.on_exposure_drag = None
        self._drag_source = None
        self._drag_target = None
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setToolTip('Drag the turquoise grip at a frame’s right edge to extend its hold.')

    def _handle_rect(self, item):
        rect = self.visualItemRect(item)
        return QRect(rect.right() - self.GRIP_WIDTH + 1, rect.top() + 3,
                     self.GRIP_WIDTH, max(8, rect.height() - 6))

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        if self._drag_source is not None and self._drag_target is not None:
            first, last = self._drag_source, self._drag_target
            if last > first:
                for index in range(first + 1, min(last + 1, self.count())):
                    preview_rect = self.visualItemRect(self.item(index))
                    painter.fillRect(preview_rect, QColor(100, 196, 204, 95))
                    painter.setPen(QPen(QColor('#15d4e6'), 2))
                    painter.drawRect(preview_rect.adjusted(1, 1, -2, -2))
            painter.setPen(QPen(QColor('#e9fdff'), 1))
            painter.drawText(self.viewport().rect().adjusted(6, 3, -6, -3),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
                f'Hold through frame {last + 1}' if last > first else 'Drag right to extend')
        for row in range(self.count()):
            item = self.item(row)
            rect = self.visualItemRect(item)
            if not rect.isValid() or not rect.intersects(self.viewport().rect()):
                continue
            handle = self._handle_rect(item)
            active = self._drag_source == row
            painter.fillRect(handle, QColor('#176f75') if active else QColor('#328f98'))
            painter.setPen(QPen(QColor('#f7fcfd'), 2))
            # A visible grip, independent of frame thumbnail artwork.
            cx, cy = handle.center().x(), handle.center().y()
            for dx in (-4, 0, 4):
                painter.drawLine(cx + dx, cy - 8, cx + dx, cy + 8)
        painter.end()

    def mouseMoveEvent(self, event):
        if self._drag_source is not None:
            hovered = self.itemAt(event.position().toPoint())
            self._drag_target = self.row(hovered) if hovered is not None else None
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.viewport().update()
            event.accept()
            return
        item = self.itemAt(event.position().toPoint())
        if item is not None and self._handle_rect(item).contains(event.position().toPoint()):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.setToolTip(f'Drag grip on frame {self.row(item) + 1} to a later frame to extend its hold')
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not event.modifiers():
            item = self.itemAt(event.position().toPoint())
            if item is not None and self._handle_rect(item).contains(event.position().toPoint()):
                self._drag_source = self.row(item)
                self._drag_target = self._drag_source
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self.viewport().update()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_source is not None:
            source = self._drag_source
            self._drag_source = None
            self._drag_target = None
            self.unsetCursor()
            target = self.itemAt(event.position().toPoint())
            self.viewport().update()
            if target is not None and self.on_exposure_drag:
                self.on_exposure_drag(source, self.row(target))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if self._drag_source is None:
            self.unsetCursor()
        super().leaveEvent(event)


class HSVDisc(QWidget):
    """Compact hue ring plus square saturation/value plane (pure Qt paint)."""
    changed = Signal(QColor)

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.setFixedSize(240, 240)
        self._color = QColor(color)
        self._hue = max(0, self._color.hue())
        self._sat = self._color.hsvSaturation()
        self._value = self._color.value()
        self._sv_cache = None
        self._drag_mode = None

    def set_color(self, color):
        new_color = QColor(color)
        if not new_color.isValid(): return
        hue = new_color.hue()
        if hue >= 0 and hue != self._hue:
            self._hue = hue
            self._sv_cache = None
        self._sat, self._value = new_color.hsvSaturation(), new_color.value()
        self._color = new_color
        self.update()

    def _emit(self):
        self._color = QColor.fromHsv(self._hue, self._sat, self._value)
        self.changed.emit(QColor(self._color))
        self.update()

    def _sv_image(self):
        if self._sv_cache is None:
            result = QImage(126, 126, QImage.Format.Format_RGB32)
            for y in range(126):
                v = round(255 * (1 - y / 125))
                for x in range(126):
                    result.setPixelColor(x, y, QColor.fromHsv(self._hue, round(255*x/125), v))
            self._sv_cache = result
        return self._sv_cache

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cx, cy = 120, 120
        for hue in range(360):
            radians = math.radians(hue - 90)
            painter.setPen(QPen(QColor.fromHsv(hue, 255, 255), 3))
            painter.drawLine(QPointF(cx + 98*math.cos(radians), cy + 98*math.sin(radians)),
                             QPointF(cx + 111*math.cos(radians), cy + 111*math.sin(radians)))
        theta = math.radians(self._hue - 90)
        spot = QPointF(cx + 105*math.cos(theta), cy + 105*math.sin(theta))
        painter.setPen(QPen(QColor('#ffffff'), 2.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(spot, 7, 7)
        painter.drawImage(57, 57, self._sv_image())
        painter.setPen(QPen(QColor('#b9bec7'), 1))
        painter.drawRect(QRect(56, 56, 127, 127))
        select = QPointF(57 + 125 * self._sat/255, 57 + 125*(1-self._value/255))
        painter.setPen(QPen(QColor('#ffffff') if self._value < 125 else QColor('#171c27'), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(select, 5.5, 5.5)
        painter.end()

    def _pick(self, pos, force_mode=None):
        x, y = pos.x(), pos.y()
        radius = math.hypot(x-120, y-120)
        mode = force_mode or ('hue' if 89 <= radius <= 120 else 'sv' if 57 <= x <= 183 and 57 <= y <= 183 else None)
        if mode == 'hue':
            self._hue = round((math.degrees(math.atan2(y-120, x-120)) + 90) % 360) % 360
            self._sv_cache = None
        elif mode == 'sv':
            self._sat = round(255 * max(0, min(1, (x-57)/125)))
            self._value = round(255 * max(0, min(1, 1-(y-57)/125)))
        else:
            return False
        self._emit()
        return mode

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_mode = self._pick(event.position())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_mode and event.buttons() & Qt.MouseButton.LeftButton:
            self._pick(event.position(), self._drag_mode)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_mode = None


class ColorStudioDialog(QDialog):
    """Disc/harmony/palettes/values, with named user palettes in QSettings."""
    def __init__(self, color, preferences, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Color Studio')
        self.resize(350, 440)
        self.setMinimumWidth(305)
        self.preferences = preferences
        self.color = QColor(color)
        try:
            stored = json.loads(str(preferences.value('color_studio/palettes', '{}')))
            self.palettes = {str(k)[:45]: [v for v in vals if QColor(v).isValid()][:40]
                             for k, vals in stored.items() if isinstance(vals, list)}
        except (ValueError, TypeError, AttributeError):
            self.palettes = {}
        if not self.palettes:
            self.palettes = {'Starter': ['#000000','#ffffff','#d44444','#f6bd4f',
                                          '#62aa71','#438bc5','#7256a8','#d886bb']}
        self._updating = False
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.chip = QLabel()
        self.chip.setFixedSize(32, 32)
        self.hex_edit = QLineEdit()
        self.hex_edit.setMaxLength(7)
        self.hex_edit.setPlaceholderText('#RRGGBB')
        self.hex_edit.editingFinished.connect(self._hex_changed)
        header.addWidget(self.chip)
        header.addWidget(self.hex_edit, 1)
        layout.addLayout(header)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        disc_page = QWidget()
        disc_layout = QVBoxLayout(disc_page)
        self.disc = HSVDisc(self.color)
        self.disc.changed.connect(self._set_color)
        disc_layout.addWidget(self.disc, alignment=Qt.AlignmentFlag.AlignCenter)
        disc_layout.addWidget(QLabel('Ring: hue    •    Square: saturation and brightness'),
                              alignment=Qt.AlignmentFlag.AlignCenter)
        self.tabs.addTab(disc_page, 'Disc')

        harmony_page = QWidget()
        harmony_layout = QVBoxLayout(harmony_page)
        harmony_layout.addWidget(QLabel('Choose a harmony based on your current color:'))
        self.harmony_type = QComboBox()
        self.harmony_type.addItems(['Complementary','Analogous','Triadic'])
        self.harmony_type.currentIndexChanged.connect(self._update_harmony)
        harmony_layout.addWidget(self.harmony_type)
        self.harmony_swatches = QHBoxLayout()
        harmony_layout.addLayout(self.harmony_swatches)
        harmony_layout.addStretch()
        self.tabs.addTab(harmony_page, 'Harmony')

        palette_page = QWidget()
        palette_layout = QVBoxLayout(palette_page)
        self.palette_choice = QComboBox()
        self.palette_choice.addItems(sorted(self.palettes))
        self.palette_choice.currentIndexChanged.connect(self._on_palette_changed)
        # A tab change does not change the combo index. Refresh explicitly when
        # returning to Palettes, including the very first visit.
        self.tabs.currentChanged.connect(self._on_color_tab_changed)
        self.selected_palette_color = None
        palette_layout.addWidget(self.palette_choice)
        self.swatch_grid = QGridLayout()
        palette_layout.addLayout(self.swatch_grid)
        palette_layout.addStretch()
        palette_commands = QHBoxLayout()
        make = QPushButton('New palette')
        make.clicked.connect(self._new_palette)
        add = QPushButton('Add current color')
        add.clicked.connect(self._save_color)
        self.remove_swatch_button = QPushButton('Remove selected')
        self.remove_swatch_button.setToolTip('Select a palette swatch, then remove it. You can also right-click a swatch.')
        self.remove_swatch_button.clicked.connect(self._remove_selected_swatch)
        palette_commands.addWidget(make)
        palette_commands.addWidget(add)
        palette_layout.addLayout(palette_commands)
        # Keep the layout usable on the Surface Pro 3 and narrow windows.
        palette_layout.addWidget(self.remove_swatch_button)
        self.tabs.addTab(palette_page, 'Palettes')

        values_page = QWidget()
        values_layout = QFormLayout(values_page)
        self.rgb_inputs = []
        for channel, label in enumerate(('Red', 'Green', 'Blue')):
            control = QSpinBox()
            control.setRange(0, 255)
            control.valueChanged.connect(lambda value, idx=channel: self._rgb_changed(idx, value))
            values_layout.addRow(label, control)
            self.rgb_inputs.append(control)
        system_picker = QPushButton('System color picker…')
        system_picker.clicked.connect(self._native_picker)
        values_layout.addRow(system_picker)
        self.tabs.addTab(values_page, 'Values')

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._set_color(self.color)
        self._render_palette()  # Populate the initially selected palette before opening the tab.

    def current_color(self):
        return QColor(self.color)

    def _set_color(self, color):
        if self._updating or not color.isValid():
            return
        self._updating = True
        self.color = QColor(color)
        self.disc.set_color(color)
        self.chip.setStyleSheet('background-color: %s; border: 1px solid gray; border-radius: 6px;' % color.name())
        self.hex_edit.setText(color.name().upper())
        for spin, value in zip(self.rgb_inputs, (color.red(), color.green(), color.blue())):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
        self._updating = False
        self._update_harmony()

    def _hex_changed(self):
        text = self.hex_edit.text().strip()
        if not text.startswith('#'): text = '#' + text
        c = QColor(text)
        if c.isValid() and len(text) == 7:
            self._set_color(c)
        else:
            self.hex_edit.setText(self.color.name().upper())

    def _rgb_changed(self, index, value):
        if not self._updating:
            self._set_color(QColor(*(v.value() for v in self.rgb_inputs)))

    def _native_picker(self):
        color = QColorDialog.getColor(self.color, self, 'Choose a color')
        if color.isValid(): self._set_color(color)

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None: item.widget().deleteLater()

    def _update_harmony(self, *_):
        self._clear_layout(self.harmony_swatches)
        offsets = {'Complementary': [0, 180], 'Analogous': [-30, 0, 30],
                   'Triadic': [0, 120, 240]}[self.harmony_type.currentText()]
        base_hue = max(0, self.color.hue())
        sat = max(60, self.color.hsvSaturation())
        value = max(80, self.color.value())
        for offset in offsets:
            tone = QColor.fromHsv((base_hue + offset) % 360, sat, value)
            button = QPushButton(tone.name().upper())
            button.setMinimumHeight(72)
            button.setToolTip('Use ' + tone.name().upper())
            button.setStyleSheet('QPushButton { background:%s; color:%s; border:1px solid gray; border-radius:7px; }' %
                                 (tone.name(), '#ffffff' if tone.value() < 170 else '#151515'))
            button.clicked.connect(lambda checked=False, c=QColor(tone): self._set_color(c))
            self.harmony_swatches.addWidget(button)

    def _persist_palettes(self):
        self.preferences.setValue('color_studio/palettes', json.dumps(self.palettes))

    def _new_palette(self):
        name, ok = QInputDialog.getText(self, 'New palette', 'Palette name:')
        name = name.strip()[:45]
        if not ok or not name: return
        if name in self.palettes:
            QMessageBox.information(self, 'Palette exists', 'Choose a different name.')
            return
        if len(self.palettes) >= 15:
            QMessageBox.warning(self, 'Palette limit', 'Maximum 15 palettes.')
            return
        self.palettes[name] = []
        self._persist_palettes()
        self.palette_choice.addItem(name)
        self.palette_choice.setCurrentText(name)
        self.selected_palette_color = None
        self._render_palette()

    def _save_color(self):
        name = self.palette_choice.currentText()
        if not name: return
        colors = self.palettes.setdefault(name, [])
        if self.color.name() not in colors:
            if len(colors) >= 40:
                QMessageBox.warning(self, 'Palette full', 'Maximum 40 colors per palette.')
                return
            colors.append(self.color.name())
            self._persist_palettes()
        self._render_palette()

    def _on_palette_changed(self, *_):
        self.selected_palette_color = None
        self._render_palette()

    def _on_color_tab_changed(self, index):
        if self.tabs.tabText(index) == 'Palettes':
            self._render_palette()

    def _choose_palette_swatch(self, color):
        self.selected_palette_color = color
        self._set_color(QColor(color))
        self._render_palette()

    def _remove_selected_swatch(self):
        name = self.palette_choice.currentText()
        color = self.selected_palette_color
        if not name or not color or color not in self.palettes.get(name, []):
            return
        # Removing a saved swatch must not alter the active drawing color.
        self.palettes[name].remove(color)
        self.selected_palette_color = None
        self._persist_palettes()
        self._render_palette()

    def _swatch_context_menu(self, button, color, position):
        menu = QMenu(self)
        remove = menu.addAction('Remove color from palette')
        chosen = menu.exec(button.mapToGlobal(position))
        if chosen == remove:
            self.selected_palette_color = color
            self._remove_selected_swatch()

    def _render_palette(self, *_):
        self._clear_layout(self.swatch_grid)
        name = self.palette_choice.currentText()
        colors = self.palettes.get(name, [])
        if self.selected_palette_color not in colors:
            self.selected_palette_color = None
        self.remove_swatch_button.setEnabled(self.selected_palette_color is not None)
        for i, hex_color in enumerate(colors):
            button = QPushButton('')
            button.setToolTip(hex_color.upper() + ' • click to select • right-click to remove')
            button.setFixedSize(43, 39)
            border = '3px solid #39b6ef' if hex_color == self.selected_palette_color else '1px solid #89909b'
            button.setStyleSheet('background:%s; border:%s; border-radius:5px;' % (hex_color, border))
            button.clicked.connect(lambda checked=False, c=hex_color: self._choose_palette_swatch(c))
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(
                lambda pos, b=button, c=hex_color: self._swatch_context_menu(b, c, pos))
            self.swatch_grid.addWidget(button, i//6, i%6)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project_path = None
        self.project_active = False
        self.resize(1370, 930)
        self.play_timer = QTimer(self)
        self.play_timer.setInterval(15)
        self.play_timer.timeout.connect(self._playback_tick)
        self.play_clock = QElapsedTimer()
        self.play_start_frame = 0
        self._last_audio_loop = 0
        self._refreshing_frames = False
        self.audio_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_player.setAudioOutput(self.audio_output)
        self.audio_temp = tempfile.TemporaryDirectory(prefix='las-audio-')
        self.audio_mute = False
        self.focus_mode = False
        self.focus_restore = {}
        self.preferences = QSettings("LinuxAnimationStudio", "LinuxAnimationStudio")
        # Workspace layouts are UI preferences only, never part of the .las document.
        # Every fresh application launch begins in the uncluttered Drawing workspace.
        self.workspace_mode = 'Drawing'
        self._workspace_restoring = False
        self._workspace_anchor_serial = 0
        self.custom_shortcuts = {}
        self.timeline_selected_frames = []
        root = QWidget()
        vertical = QVBoxLayout(root)
        toolbar = QHBoxLayout()
        self.canvas = Canvas()
        self.status = QLabel('Wacom stylus ready | Select a tool and draw.')
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.canvas.diagnostic.connect(self.status.setText)
        self.canvas.dirty_changed.connect(self.refresh_title)
        self.canvas.document_changed.connect(self.refresh_layers)
        self.canvas.frames_changed.connect(self.refresh_frames)
        self.canvas.playhead_changed.connect(self.refresh_playhead)

        self.toolbar_buttons = []
        def button(text, callback):
            item = QPushButton(text)
            item.clicked.connect(callback)
            toolbar.addWidget(item)
            self.toolbar_buttons.append(item)
            return item

        # The main menu bar keeps the full file/export commands. The drawing
        # toolbar exposes only everyday actions and context-sensitive tools.
        button('New', self.new_project).setToolTip('New project')
        button('Open .las', self.open_project).setToolTip('Open project')
        self.undo_button = button('↶', self.canvas.undo)
        self.undo_button.setToolTip('Undo')
        self.redo_button = button('↷', self.canvas.redo)
        self.redo_button.setToolTip('Redo')
        self.undo_button.setEnabled(False)
        self.redo_button.setEnabled(False)
        self.canvas.history_changed.connect(self.update_history)
        toolbar.addSpacing(12)
        self.tool_buttons = {}
        for tool, label, hint in [
            ('brush', '🖌', 'Brush: click to draw, arrow for brush presets'),
            ('eraser', '⌫', 'Eraser: click to erase, arrow for size presets'),
            ('select', '▱', 'Selection: arrow for rectangle / lassos'),
            ('transform', '➤', 'Transform / move selection or active cel'),
            ('pan', '✋', 'Pan canvas')]:
            b = QToolButton()
            b.setText(label)
            b.setToolTip(hint)
            b.setCheckable(True)
            b.setMinimumSize(37, 36)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            b.clicked.connect(lambda checked=False, t=tool: self.set_tool(t))
            toolbar.addWidget(b)
            self.tool_buttons[tool] = b
        self.tool_buttons['brush'].setChecked(True)
        toolbar.addSpacing(8)
        self.color_button = button('●', self.pick_color)
        self.color_button.setToolTip('Choose drawing color')
        self.color_button.setFixedSize(39, 36)
        self.update_color_swatch()
        toolbar.addStretch()
        self.workspace_picker = QComboBox()
        self.workspace_picker.addItems(['Drawing', 'Animation'])
        self.workspace_picker.setToolTip('Switch workspace layout without changing the project, frame, or drawing tools')
        self.workspace_picker.setMinimumWidth(105)
        self.workspace_picker.setMaximumWidth(132)
        self.workspace_picker.currentTextChanged.connect(self.change_workspace)
        toolbar.addWidget(self.workspace_picker)
        self.options_button = button('⚙ Tools', self.toggle_tool_options)
        self.options_button.setToolTip('Show/hide advanced brush and tool settings')
        self.layers_button = button('▤ Layers', self.toggle_layers_panel)
        self.layers_button.setToolTip('Show/hide layer controls')
        self.top_toolbar = QWidget()
        self.top_toolbar.setLayout(toolbar)
        vertical.addWidget(self.top_toolbar)

        content = QHBoxLayout()
        left_panel = QWidget()
        left = QVBoxLayout(left_panel)
        left.setContentsMargins(5, 5, 5, 5)
        left.addWidget(QLabel('TOOLS'))
        self.selection_mode_picker = QComboBox()
        self.selection_mode_picker.addItem('Rectangle', 'rectangle')
        self.selection_mode_picker.addItem('Freehand Lasso', 'freehand')
        self.selection_mode_picker.addItem('Polygonal Lasso', 'polygonal')
        self.selection_mode_picker.currentIndexChanged.connect(self._selection_mode_changed)
        left.addWidget(QLabel('Selection mode'))
        left.addWidget(self.selection_mode_picker)
        transform_buttons = QHBoxLayout()
        apply_button = QPushButton('Apply Transform')
        apply_button.clicked.connect(lambda: self.canvas.apply_transform(keep_selection=False))
        transform_buttons.addWidget(apply_button)
        cancel_button = QPushButton('Cancel Transform')
        cancel_button.clicked.connect(self.canvas.cancel_transform)
        transform_buttons.addWidget(cancel_button)
        left.addLayout(transform_buttons)
        self.motion_transform_button = QPushButton('Transform Motion Object')
        self.motion_transform_button.clicked.connect(self.activate_motion_transform)
        left.addWidget(self.motion_transform_button)
        left.addWidget(QLabel('Brush / eraser diameter'))
        size_row = QHBoxLayout()
        self.size_input = QSpinBox()
        self.size_input.setRange(1, 500)
        self.size_input.setValue(self.canvas.size)
        self.size_input.setSuffix(' px')
        self.size_input.valueChanged.connect(self.change_size)
        self.size_input.editingFinished.connect(self.return_canvas_focus)
        size_row.addWidget(self.size_input)
        left.addLayout(size_row)
        left.addWidget(QLabel('Brush preset'))
        self.brush_select = QComboBox()
        self.brush_select.addItems(['Round', 'Pencil', 'Ink', 'Airbrush'])
        self.brush_select.currentTextChanged.connect(self.change_brush_preset)
        left.addWidget(self.brush_select)
        self.custom_picker = QComboBox()
        self.custom_picker.addItem('Built-in preset', None)
        for ident, brush in sorted(self.canvas.custom_brushes.items(), key=lambda item: item[1]['name'].lower()):
            self.custom_picker.addItem(brush['name'], ident)
        self.custom_picker.currentIndexChanged.connect(self.choose_custom_brush)
        left.addWidget(QLabel('Custom brush'))
        left.addWidget(self.custom_picker)
        create_selected = QPushButton('Brush from Selection')
        create_selected.clicked.connect(self.make_custom_brush_from_selection)
        left.addWidget(create_selected)
        create_layer = QPushButton('Brush from Active Layer')
        create_layer.clicked.connect(self.make_custom_brush_from_layer)
        left.addWidget(create_layer)
        self.spacing_input = QSpinBox()
        self.spacing_input.setRange(1, 400)
        self.spacing_input.setSuffix(' %')
        self.spacing_input.setValue(30)
        self.spacing_input.valueChanged.connect(self.change_custom_spacing)
        left.addWidget(QLabel('Stamp spacing (% of diameter)'))
        left.addWidget(self.spacing_input)
        left.addWidget(QLabel('Custom brush dynamics'))
        self.follow_direction = QCheckBox('Rotate along stroke')
        self.follow_direction.toggled.connect(lambda v: self.change_custom_dynamic('follow_direction', v))
        left.addWidget(self.follow_direction)
        self.dynamics_controls = {}
        for key, title, maximum in [('rotation_jitter','Random rotation (degrees)',180),
                                    ('scatter','Scatter (% of size)',200),
                                    ('pressure_size','Pressure affects size (%)',100),
                                    ('pressure_opacity','Pressure affects opacity (%)',100)]:
            left.addWidget(QLabel(title))
            widget = QSpinBox()
            widget.setRange(0, maximum)
            widget.valueChanged.connect(lambda value, k=key: self.change_custom_dynamic(k, value))
            left.addWidget(widget)
            self.dynamics_controls[key] = widget
        self.custom_preview = QLabel('Brush preview')
        self.custom_preview.setMinimumHeight(75)
        self.custom_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(self.custom_preview)
        delete_custom = QPushButton('Delete Custom Brush')
        delete_custom.clicked.connect(self.delete_custom_brush)
        left.addWidget(delete_custom)
        left.addWidget(QLabel('Brush opacity'))
        self.brush_opacity = QSpinBox()
        self.brush_opacity.setRange(1, 100)
        self.brush_opacity.setSuffix(' %')
        self.brush_opacity.setValue(100)
        self.brush_opacity.valueChanged.connect(self.change_brush_opacity)
        self.brush_opacity.editingFinished.connect(self.return_canvas_focus)
        left.addWidget(self.brush_opacity)
        left.addStretch()
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        settings_scroll.setMinimumWidth(160)
        settings_scroll.setMaximumWidth(250)
        settings_scroll.setWidget(left_panel)
        self.settings_scroll = settings_scroll
        content.addWidget(settings_scroll)
        settings_scroll.hide()  # Canvas first; ⚙ Tools reveals advanced settings.

        scroll = PannableScrollArea()
        self.canvas_scroll = scroll
        scroll.setWidget(self.canvas)
        scroll.on_canvas_zoom = lambda zoom: self.status.setText(f'Canvas zoom: {zoom * 100:.0f}%')
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        content.addWidget(scroll, 1)

        right = QVBoxLayout()
        right.addWidget(QLabel('Layers (top to bottom)'))
        self.layers_list = QListWidget()
        self.layers_list.setMinimumWidth(185)
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
        right.addWidget(QLabel('Track behavior'))
        self.layer_mode = QComboBox()
        self.layer_mode.addItem('Animated (independent cels)', 'animated')
        self.layer_mode.addItem('Static (same art every frame)', 'static')
        self.layer_mode.currentIndexChanged.connect(self.change_layer_mode)
        right.addWidget(self.layer_mode)
        right.addWidget(QLabel('Active layer opacity'))
        self.opacity_input = QSpinBox()
        self.opacity_input.setRange(0, 100)
        self.opacity_input.setSuffix(' %')
        self.opacity_input.setValue(100)
        self.opacity_input.valueChanged.connect(self.canvas.set_opacity)
        self.opacity_input.editingFinished.connect(self.return_canvas_focus)
        right.addWidget(self.opacity_input)
        self.right_panel = QWidget()
        self.right_panel.setLayout(right)
        content.addWidget(self.right_panel)
        self.right_panel.hide()  # Open layers from the compact toolbar.
        self.workspace = QWidget()
        self.workspace.setLayout(content)
        vertical.addWidget(self.workspace, 1)
        self.welcome = QWidget()
        welcome_layout = QVBoxLayout(self.welcome)
        welcome_layout.addStretch()
        heading = QLabel('Linux Animation Studio\nNo project open')
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet('font-size: 22px; font-weight: bold;')
        welcome_layout.addWidget(heading)
        new_button = QPushButton('New Project')
        new_button.clicked.connect(self.new_project)
        welcome_layout.addWidget(new_button, alignment=Qt.AlignmentFlag.AlignCenter)
        open_button = QPushButton('Open Project')
        open_button.clicked.connect(self.open_project)
        welcome_layout.addWidget(open_button, alignment=Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addStretch()
        vertical.addWidget(self.welcome, 1)
        self.welcome.hide()

        # Keep the timeline in a bounded viewport.  The v0.17 Ignored size policy
        # allowed Qt to allocate zero pixels while the timeline was still visible.
        # A scroll area makes its controls reachable without increasing the window's
        # minimum height on compact displays.
        self.timeline_container = QScrollArea()
        self.timeline_container.setWidgetResizable(True)
        self.timeline_container.setMinimumHeight(120)
        self.timeline_container.setMaximumHeight(280)
        self.timeline_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.timeline_content = QWidget()
        timeline = QVBoxLayout(self.timeline_content)
        timeline.setContentsMargins(4, 3, 4, 3)
        # High-frequency transport stays outside the scrolling detail panels.
        timeline_tabs = QTabWidget()
        cel_page = QWidget(); cel_page_layout = QVBoxLayout(cel_page)
        onion_page = QWidget(); onion_page_layout = QVBoxLayout(onion_page)
        audio_page = QWidget(); audio_page_layout = QVBoxLayout(audio_page)
        motion_page = QWidget(); motion_page_layout = QVBoxLayout(motion_page)
        timeline_tabs.addTab(cel_page, "Cels")
        timeline_tabs.addTab(onion_page, "Onion Skins")
        timeline_tabs.addTab(audio_page, "Audio")
        timeline_tabs.addTab(motion_page, "Motion")
        frame_controls = QHBoxLayout()
        for label, func in [('⏮ First', lambda: self.go_to_end_frame(first=True)),
                            ('Previous', lambda: self.canvas.change_frame(self.canvas.frame_index-1)),
                            ('Next', lambda: self.canvas.change_frame(self.canvas.frame_index+1)),
                            ('Last ⏭', lambda: self.go_to_end_frame(first=False)),
                            ('+ Blank', lambda: self.canvas.add_frame(False)),
                            ('Duplicate', lambda: self.canvas.add_frame(True)),
                            ('Delete', self.canvas.delete_frame)]:
            b = QPushButton(label)
            b.clicked.connect(func)
            frame_controls.addWidget(b)
        frame_controls.addWidget(QLabel('FPS:'))
        self.fps_input = QSpinBox()
        self.fps_input.setRange(1, 60)
        self.fps_input.setValue(12)
        self.fps_input.valueChanged.connect(self.change_fps)
        frame_controls.addWidget(self.fps_input)
        self.frame_label = QLabel('Frame 1 / 1')
        frame_controls.addWidget(self.frame_label)
        frame_controls.addWidget(QLabel('Go to:'))
        self.frame_jump = QSpinBox()
        self.frame_jump.setRange(1, 120)
        self.frame_jump.valueChanged.connect(lambda n: self.canvas.change_frame(n - 1))
        frame_controls.addWidget(self.frame_jump)
        frame_controls.addStretch()
        timeline.addLayout(frame_controls)
        cel_controls = QHBoxLayout()
        cel_controls.addWidget(QLabel('Active layer cel:'))
        self.hold_length = QSpinBox()
        self.hold_length.setRange(2, 120)
        self.hold_length.setValue(3)
        self.hold_length.setToolTip('Total exposure duration, including current frame')
        cel_controls.addWidget(self.hold_length)
        for title, callback in [('Extend Hold', self.extend_hold),
                                ('Break / New Cel', self.split_hold),
                                ('Link From…', self.link_from),
                                ('Unlink', self.unlink_current)]:
            button = QPushButton(title)
            button.clicked.connect(callback)
            cel_controls.addWidget(button)
        cel_page_layout.addLayout(cel_controls)
        exact = QPushButton("Extend Hold To Frame…")
        exact.clicked.connect(self.extend_hold_to_frame)
        cel_page_layout.addWidget(exact)
        self.batch_menu_button = QPushButton("Apply to Selected Frames…")
        self.batch_menu_button.clicked.connect(self.batch_frame_action)
        cel_page_layout.addWidget(self.batch_menu_button)
        self.multi_edit_checkbox = QCheckBox('Multi-frame Edit: draw / erase / transform selected frames')
        self.multi_edit_checkbox.setToolTip('Applies edits to unique cels on the active layer; linked exposures are edited once.')
        self.multi_edit_checkbox.setChecked(False)
        self.multi_edit_checkbox.toggled.connect(self._set_multi_edit)
        cel_page_layout.addWidget(self.multi_edit_checkbox)
        # Always-visible warning, even when the Cels settings tab is not selected.
        self.multi_edit_indicator = QLabel('Single-frame drawing')
        self.multi_edit_indicator.setToolTip('Multi-frame editing is off; only the current frame is changed.')
        self.multi_edit_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.multi_edit_indicator.setStyleSheet('QLabel { color: #61646a; padding: 3px 10px; border: 1px solid #8a8d92; border-radius: 4px; }')
        frame_controls.addWidget(self.multi_edit_indicator)

        self.track_visualization = QLabel('Cel tracks')
        self.track_visualization.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.track_visualization.setWordWrap(True)
        cel_page_layout.addWidget(self.track_visualization)
        play_controls = QHBoxLayout()
        self.play_button = QPushButton('▶ Play')
        self.play_button.clicked.connect(self.toggle_playback)
        play_controls.addWidget(self.play_button)
        self.stop_button = QPushButton('■ Stop')
        self.stop_button.clicked.connect(self.stop_playback)
        play_controls.addWidget(self.stop_button)
        self.loop_checkbox = QCheckBox('Loop')
        self.loop_checkbox.setChecked(True)
        self.loop_checkbox.toggled.connect(self.set_loop)
        play_controls.addWidget(self.loop_checkbox)
        self.onion_checkbox = QCheckBox('Onion skins (previous red, next green)')
        self.onion_checkbox.toggled.connect(self.set_onion_enabled)
        play_controls.addWidget(self.onion_checkbox)
        play_controls.addWidget(QLabel('Ghost opacity:'))
        self.onion_spin = QSpinBox()
        self.onion_spin.setRange(0, 100)
        self.onion_spin.setSuffix(' %')
        self.onion_spin.setValue(35)
        self.onion_spin.valueChanged.connect(self.set_onion_opacity)
        self.onion_spin.editingFinished.connect(self.return_canvas_focus)
        play_controls.addWidget(self.onion_spin)
        play_controls.addStretch()
        timeline.addLayout(play_controls)
        ranges = QHBoxLayout()
        ranges.addWidget(QLabel('Previous ghosts'))
        self.onion_previous_input = QSpinBox()
        self.onion_previous_input.setRange(0, 6)
        self.onion_previous_input.setValue(self.canvas.onion_previous)
        self.onion_previous_input.valueChanged.connect(lambda value: self.change_onion_range('previous', value))
        ranges.addWidget(self.onion_previous_input)
        ranges.addWidget(QLabel('Next ghosts'))
        self.onion_next_input = QSpinBox()
        self.onion_next_input.setRange(0, 6)
        self.onion_next_input.setValue(self.canvas.onion_next)
        self.onion_next_input.valueChanged.connect(lambda value: self.change_onion_range('next', value))
        ranges.addWidget(self.onion_next_input)
        onion_page_layout.addLayout(ranges)
        audio_controls = QHBoxLayout()
        self.audio_import_button = QPushButton('Import Audio WAV/MP3')
        self.audio_import_button.clicked.connect(self.import_audio)
        audio_controls.addWidget(self.audio_import_button)
        self.audio_remove_button = QPushButton('Remove Audio')
        self.audio_remove_button.clicked.connect(self.remove_audio)
        audio_controls.addWidget(self.audio_remove_button)
        self.audio_label = QLabel('No audio imported')
        audio_controls.addWidget(self.audio_label)
        self.audio_mute_checkbox = QCheckBox('Mute')
        self.audio_mute_checkbox.toggled.connect(self.set_audio_mute)
        audio_controls.addWidget(self.audio_mute_checkbox)
        audio_controls.addWidget(QLabel('Volume'))
        self.audio_volume = QSpinBox()
        self.audio_volume.setRange(0, 100)
        self.audio_volume.setValue(100)
        self.audio_volume.valueChanged.connect(lambda v: self.audio_output.setVolume(v / 100))
        audio_controls.addWidget(self.audio_volume)
        audio_page_layout.addLayout(audio_controls)
        self.audio_wave = AudioWaveform()
        self.audio_wave.on_seek = self.seek_audio_fraction
        audio_page_layout.addWidget(self.audio_wave)
        motion_controls = QHBoxLayout()
        self.motion_create = QPushButton('Make Motion Object from Layer')
        self.motion_create.setToolTip('Moves current-frame layer pixels into a reusable motion object')
        self.motion_create.clicked.connect(self.create_motion_object)
        motion_controls.addWidget(self.motion_create)
        self.motion_select = QComboBox()
        self.motion_select.setMinimumWidth(150)
        self.motion_select.currentIndexChanged.connect(self.choose_motion_object)
        motion_controls.addWidget(self.motion_select)
        self.motion_inputs = []
        for name, low, high, value in [('X', -8192, 8192, 0), ('Y', -8192, 8192, 0),
                                      ('Scale %', 1, 400, 100), ('Angle °', -360, 360, 0)]:
            motion_controls.addWidget(QLabel(name))
            spin = QSpinBox()
            spin.setRange(low, high)
            spin.setValue(value)
            spin.setMaximumWidth(80)
            spin.editingFinished.connect(self.return_canvas_focus)
            motion_controls.addWidget(spin)
            self.motion_inputs.append(spin)
        add_key = QPushButton('Set Keyframe')
        add_key.clicked.connect(self.set_motion_keyframe)
        motion_controls.addWidget(add_key)
        remove_key = QPushButton('Remove Keyframe')
        remove_key.clicked.connect(self.remove_motion_keyframe)
        motion_controls.addWidget(remove_key)
        motion_page_layout.addLayout(motion_controls)
        self.canvas.motion_changed.connect(self.refresh_motion)
        self.frame_list = ExposureFrameList()
        self.frame_list.on_exposure_drag = self.drag_exposure
        self.frame_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.frame_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.frame_list.setFlow(QListWidget.Flow.LeftToRight)
        self.frame_list.setWrapping(False)
        self.frame_list.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(90,60))
        self.frame_list.setFixedHeight(108)
        self.frame_list.setSpacing(5)
        self.frame_list.currentRowChanged.connect(self._timeline_current_changed)
        self.frame_list.itemSelectionChanged.connect(self._timeline_selection_changed)
        grip_hint = QLabel('Hold exposure: drag the turquoise grip at the right edge of a frame onto a later frame.')
        grip_hint.setStyleSheet('color: #328f98; font-size: 10px;')
        timeline.addWidget(grip_hint)
        timeline.addWidget(self.frame_list)
        timeline.addWidget(timeline_tabs)
        # A visible horizontal frame strip; audio/cel controls remain in tabs.
        self.timeline_container.setMaximumHeight(290)
        self.timeline_toggle = QPushButton('Hide Animation Timeline')
        self.timeline_toggle.clicked.connect(self.toggle_timeline)
        vertical.addWidget(self.timeline_toggle)
        self.timeline_container.setWidget(self.timeline_content)
        vertical.addWidget(self.timeline_container, 0)
        vertical.addWidget(self.status)
        self.setCentralWidget(root)
        self._build_tool_menus()
        saved_eraser = self.preferences.value('brush_library/eraser_size', 48, type=int)
        if 1 <= saved_eraser <= 500:
            self.canvas.eraser_size = saved_eraser
        saved_brush = str(self.preferences.value('brush_library/brush', 'Round'))
        if saved_brush.startswith('custom:'):
            index = self.custom_picker.findData(saved_brush[7:])
            if index >= 0:
                self.custom_picker.setCurrentIndex(index)
        elif saved_brush in self.canvas.brush_settings:
            self.brush_select.setCurrentText(saved_brush)
        self.refresh_layers()
        self.refresh_frames()
        self.refresh_title()
        filemenu = self.menuBar().addMenu('&File')
        for title, callback, shortcut in [
            ('New Project', self.new_project, 'Ctrl+N'),
            ('Open Project', self.open_project, 'Ctrl+O'),
            ('Save Project', self.save_project, 'Ctrl+S'),
            ('Save Project As', self.save_project_as, 'Ctrl+Shift+S'),
            ('Close Project', self.close_project, 'Ctrl+W'),
            ('Import Image as Layer...', self.import_image_layer, 'Ctrl+I'),
            ('Export...', self.export_animation, 'Ctrl+E'),
            ('Export Current Frame PNG', self.export_png, None),
            ('Quit', self.close, 'Ctrl+Q'),
        ]:
            action = filemenu.addAction(title)
            action.triggered.connect(callback)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
        editmenu = self.menuBar().addMenu('&Edit')
        editmenu.addAction('Keyboard Shortcuts…', self.show_shortcut_preferences)
        helpmenu = self.menuBar().addMenu('&Help')
        helpmenu.addAction('About Linux Animation Studio', self.show_about)
        self._set_project_active(False)
        self._refresh_tool_icons()
        self._shortcut_defs = [
            ('Undo', 'Ctrl+Z', self.canvas.undo),
            ('Redo', 'Ctrl+Shift+Z', self.canvas.redo),
            ('Redo Alternative', 'Ctrl+Y', self.canvas.redo),
            ('Brush Smaller', '[', lambda: self.adjust_brush(-1)),
            ('Brush Larger', ']', lambda: self.adjust_brush(1)),
            ('Brush Tool', 'B', lambda: self._tool_shortcut('brush')),
            ('Cycle Brush Presets', 'Shift+B', self._cycle_brush_preset),
            ('Eraser Tool', 'E', lambda: self._tool_shortcut('eraser')),
            ('Rectangle Marquee', 'M', lambda: self._tool_shortcut('select', 'rectangle')),
            ('Freehand Lasso', 'L', lambda: self._tool_shortcut('select', 'freehand')),
            ('Cycle Lasso Tools', 'Shift+L', self._cycle_lasso),
            ('Transform Tool', 'T', lambda: self._tool_shortcut('transform')),
            ('Hand / Pan Tool', 'H', lambda: self._tool_shortcut('pan')),
            ('Select All', 'Ctrl+A', self.canvas.select_all),
            ('Deselect', 'Ctrl+D', self.canvas.deselect),
            ('Previous Frame', ',', lambda: self.navigate_frame(-1)),
            ('Next Frame', '.', lambda: self.navigate_frame(1)),
            ('First Frame', '<', lambda: self.go_to_end_frame(first=True)),
            ('Last Frame', '>', lambda: self.go_to_end_frame(first=False)),
            ('Play/Pause', 'P', self.toggle_playback),
            ('Zoom In', 'Ctrl++', lambda: self.adjust_zoom(1.25)),
            ('Zoom In Alternative', 'Ctrl+=', lambda: self.adjust_zoom(1.25)),
            ('Zoom Out', 'Ctrl+-', lambda: self.adjust_zoom(0.8)),
            ('Fit Canvas', 'Ctrl+0', self.fit_zoom),
            ('Canvas Focus Mode', 'Tab', self.toggle_focus_mode),
            ('Drawing Workspace', 'Ctrl+1', lambda: self._select_workspace('Drawing')),
            ('Animation Workspace', 'Ctrl+2', lambda: self._select_workspace('Animation')),
        ]
        self._shortcut_objects = {}
        self._install_shortcuts()
        # Existing alternative frame navigation remains unchanged.
        for seq, fn in [('Alt+Left', lambda: self.navigate_frame(-1)), ('Alt+Right', lambda: self.navigate_frame(1))]:
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(fn)

    def create_motion_object(self):
        try:
            self.pause_playback()
            self.canvas.make_motion_from_layer()
            self.refresh_motion()
        except Exception as exc:
            QMessageBox.warning(self, 'Motion object', str(exc))

    def choose_motion_object(self, index):
        if index >= 0:
            self.canvas.active_motion_id = self.motion_select.itemData(index)
            self.refresh_motion()

    def refresh_motion(self):
        self.motion_select.blockSignals(True)
        self.motion_select.clear()
        for obj in self.canvas.motion_objects:
            self.motion_select.addItem(obj.name, obj.id)
        for i, obj in enumerate(self.canvas.motion_objects):
            if obj.id == self.canvas.active_motion_id:
                self.motion_select.setCurrentIndex(i)
                break
        self.motion_select.blockSignals(False)
        obj = self.canvas.active_motion()
        values = interpolated_transform(obj.keys, self.canvas.frame_index) if obj else (0, 0, 100, 0)
        for spin, value in zip(self.motion_inputs, values):
            spin.blockSignals(True)
            spin.setValue(round(value))
            spin.blockSignals(False)

    def set_motion_keyframe(self):
        try:
            self.canvas.set_motion_key(*(spin.value() for spin in self.motion_inputs))
        except Exception as exc:
            QMessageBox.warning(self, 'Keyframe', str(exc))

    def remove_motion_keyframe(self):
        self.canvas.delete_motion_key()

    def return_canvas_focus(self):
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def navigate_frame(self, delta):
        if not self.canvas.playing:
            self.canvas.change_frame(self.canvas.frame_index + delta)

    def go_to_end_frame(self, first=True):
        if not self.project_active or not self.canvas.frames:
            return
        if self.canvas.playing:
            self.pause_playback()
        target = 0 if first else len(self.canvas.frames) - 1
        self.canvas.change_frame(target)
        # change_frame synchronizes both the timeline playhead and audio seek.

    def set_loop(self, enabled):
        self.canvas.loop_playback = enabled
        self.canvas._mark_dirty()

    def set_onion_enabled(self, enabled):
        self.canvas.onion_enabled = enabled
        self.canvas.update()
        self.canvas._mark_dirty()

    def set_onion_opacity(self, value):
        self.canvas.onion_opacity = value
        self.canvas.update()
        self.canvas._mark_dirty()

    def toggle_playback(self):
        if self.canvas.playing:
            self.pause_playback()
            return
        if self.canvas.drawing or self.canvas.drag_origin is not None:
            return
        self.canvas.playing = True
        if getattr(self.canvas, 'audio_bytes', None):
            self.audio_player.setPosition(round(self.canvas.frame_index * 1000 / self.canvas.fps))
            self.audio_player.play()
        self.play_start_frame = self.canvas.frame_index
        self._last_audio_loop = 0
        self.play_clock.start()
        self.play_timer.start()
        self.play_button.setText('Ⅱ Pause')
        self.canvas.update()

    def _playback_tick(self):
        if not self.canvas.playing:
            return
        count = len(self.canvas.frames)
        elapsed_frames = (self.play_clock.elapsed() * self.canvas.fps) // 1000
        absolute_frame = self.play_start_frame + elapsed_frames
        if not self.loop_checkbox.isChecked() and absolute_frame >= count:
            self.canvas.change_frame(count - 1, playback=True)
            self.pause_playback()
            return
        index = absolute_frame % count
        loops = absolute_frame // count
        if loops != self._last_audio_loop:
            self._last_audio_loop = loops
            if getattr(self.canvas, 'audio_bytes', None):
                self.audio_player.setPosition(0)
                self.audio_player.play()
        if index != self.canvas.frame_index:
            self.canvas.change_frame(index, playback=True)

    def pause_playback(self):
        self.play_timer.stop()
        self.audio_player.pause()
        self.canvas.playing = False
        self.play_button.setText('▶ Play')
        self.canvas.update()

    def stop_playback(self):
        self.pause_playback()
        self.canvas.change_frame(0, playback=True)
        self.audio_player.setPosition(0)

    def activate_motion_transform(self):
        if self.canvas.begin_transform(motion=True):
            for name, button in self.tool_buttons.items():
                button.setChecked(name == 'transform')
            self.return_canvas_focus()

    def toggle_tool_options(self):
        if not self.project_active:
            return
        self.settings_scroll.setVisible(not self.settings_scroll.isVisible())
        self._save_workspace_layout()
        self.return_canvas_focus()

    def toggle_layers_panel(self):
        if not self.project_active:
            return
        self.right_panel.setVisible(not self.right_panel.isVisible())
        self._save_workspace_layout()
        self.return_canvas_focus()

    def _brush_preview_icon(self, category, name, payload=None):
        """Create an illustrative static sample; never mutate a real canvas cel."""
        image = QImage(228, 56, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor('#f3f3f0'))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if category == 'Custom' and payload in self.canvas.custom_brushes:
            tip = self.canvas.custom_brushes[payload]['tip']
            if not tip.isNull():
                for i in range(8):
                    x, y = 17 + i * 26, 27 + round(6 * math.sin(i * .85))
                    painter.drawImage(QRect(x-13, y-13, 26, 26), tip)
        else:
            if category == 'Erasers':
                widths = {'Small eraser': 4, 'Medium eraser': 10,
                          'Large eraser': 17, 'Extra large eraser': 24}
                width = widths.get(name, 9)
            else:
                width = {'Round': 9, 'Pencil': 3, 'Ink': 6, 'Airbrush': 19}.get(name, 7)
            color = QColor('#343a46')
            if name == 'Pencil': color.setAlpha(145)
            if name == 'Airbrush': color.setAlpha(70)
            if category == 'Erasers': color = QColor('#8795aa')
            painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            path = QPainterPath(QPointF(13, 33))
            path.cubicTo(52, 8, 74, 49, 116, 25)
            path.cubicTo(152, 5, 186, 41, 213, 22)
            painter.drawPath(path)
        painter.end()
        return QIcon(QPixmap.fromImage(image))

    def _open_brush_library(self, eraser=False):
        """A compact, category-filtered library using existing brush state."""
        dialog = QDialog(self)
        dialog.setWindowTitle('Eraser Library' if eraser else 'Brush Library')
        dialog.setMinimumWidth(330)
        dialog.resize(390, 440)
        layout = QVBoxLayout(dialog)
        heading = QLabel('Choose an eraser size' if eraser else 'Choose a brush')
        layout.addWidget(heading)
        category_picker = QComboBox(dialog)
        if eraser:
            category_picker.addItem('Erasers')
        else:
            for name in ('All Brushes', 'Drawing', 'Sketching', 'Painting', 'Custom'):
                category_picker.addItem(name)
        layout.addWidget(category_picker)
        brushes = QListWidget(dialog)
        brushes.setIconSize(__import__('PySide6.QtCore', fromlist=['QSize']).QSize(170, 42))
        brushes.setSpacing(5)
        layout.addWidget(brushes, 1)
        explanation = QLabel('Previews are illustrative; the canvas uses your existing brush engine.')
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        edit_settings = QPushButton('Advanced Settings…', dialog)
        buttons.addButton(edit_settings, QDialogButtonBox.ButtonRole.ActionRole)
        layout.addWidget(buttons)

        def populate():
            brushes.clear()
            category = category_picker.currentText()
            if eraser:
                choices = [('Erasers', name, size) for name, size in
                           [('Small eraser', 15), ('Medium eraser', 45),
                            ('Large eraser', 95), ('Extra large eraser', 175)]]
            else:
                choices = [('Drawing', 'Round', 'Round'),
                           ('Sketching', 'Pencil', 'Pencil'),
                           ('Drawing', 'Ink', 'Ink'),
                           ('Painting', 'Airbrush', 'Airbrush')]
                choices += [('Custom', brush['name'], ident) for ident, brush in
                            sorted(self.canvas.custom_brushes.items(),
                                   key=lambda pair: pair[1]['name'].lower())]
            for group, name, value in choices:
                if category not in ('All Brushes', group, 'Erasers'):
                    continue
                item = QListWidgetItem(self._brush_preview_icon(group, name, value),
                                       name + (f'  ·  {value} px' if eraser else ''))
                item.setData(Qt.ItemDataRole.UserRole, (group, value))
                brushes.addItem(item)
                if eraser and value == self.canvas.eraser_size:
                    brushes.setCurrentItem(item)
                elif not eraser and ((group == 'Custom' and value == self.canvas.active_custom_brush) or
                        (group != 'Custom' and self.canvas.active_custom_brush is None and value == self.canvas.brush_preset)):
                    brushes.setCurrentItem(item)
            if brushes.currentItem() is None and brushes.count():
                brushes.setCurrentRow(0)

        def accept_selected():
            item = brushes.currentItem()
            if item is None: return
            group, value = item.data(Qt.ItemDataRole.UserRole)
            if eraser:
                self._quick_eraser(value)
                self.preferences.setValue('brush_library/eraser_size', value)
            elif group == 'Custom':
                index = self.custom_picker.findData(value)
                if index >= 0:
                    self.custom_picker.setCurrentIndex(index)
                    self.set_tool('brush')
                    self.preferences.setValue('brush_library/brush', 'custom:' + value)
            else:
                self._quick_brush(value)
                self.preferences.setValue('brush_library/brush', value)
            dialog.accept()

        category_picker.currentIndexChanged.connect(populate)
        brushes.itemDoubleClicked.connect(lambda item: accept_selected())
        buttons.accepted.connect(accept_selected)
        buttons.rejected.connect(dialog.reject)
        def show_advanced():
            dialog.reject()
            self.settings_scroll.show()
        edit_settings.clicked.connect(show_advanced)
        populate()
        dialog.exec()
        self.return_canvas_focus()

    def _build_tool_menus(self):
        """The tool icons stay compact; arrow opens a rich library."""
        brush_menu = QMenu(self)
        action = brush_menu.addAction('Open Brush Library…')
        action.triggered.connect(lambda: self._open_brush_library(False))
        brush_menu.addSeparator()
        action = brush_menu.addAction('Advanced Brush Settings…')
        action.triggered.connect(lambda: self.settings_scroll.show())
        brush_button = self.tool_buttons['brush']
        brush_button.setMenu(brush_menu)
        brush_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        brush_button.setToolTip('Brush: click to draw; arrow opens the Brush Library')

        eraser_menu = QMenu(self)
        action = eraser_menu.addAction('Open Eraser Library…')
        action.triggered.connect(lambda: self._open_brush_library(True))
        eraser_menu.addSeparator()
        action = eraser_menu.addAction('Advanced Eraser Settings…')
        action.triggered.connect(lambda: self.settings_scroll.show())
        eraser_button = self.tool_buttons['eraser']
        eraser_button.setMenu(eraser_menu)
        eraser_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        eraser_button.setToolTip('Eraser: click to erase; arrow opens eraser size library')

        selection_menu = QMenu(self)
        for name, mode in [('Rectangle', 'rectangle'), ('Freehand Lasso', 'freehand'),
                           ('Polygonal Lasso', 'polygonal')]:
            action = selection_menu.addAction(name)
            action.triggered.connect(lambda checked=False, m=mode: self._quick_selection(m))
        select_button = self.tool_buttons['select']
        select_button.setMenu(selection_menu)
        select_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

    def _quick_brush(self, preset):
        self.set_tool('brush')
        self.brush_select.setCurrentText(preset)
        self.return_canvas_focus()

    def _quick_eraser(self, size):
        self.set_tool('eraser')
        self.size_input.setValue(size)
        self._refresh_tool_icons()
        self.return_canvas_focus()

    def _quick_selection(self, mode):
        self.selection_mode_picker.setCurrentIndex(
            self.selection_mode_picker.findData(mode))
        self.set_tool('select')
        self.return_canvas_focus()

    def _selection_mode_changed(self, index):
        self.canvas.set_selection_mode(self.selection_mode_picker.itemData(index))
        self._refresh_tool_icons()

    def _small_tool_icon(self, tool):
        """Paint a legible preset representation without adding toolbar widgets."""
        img = QImage(34, 34, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        white = QColor('#eaf0fa')
        painter.setPen(QPen(white, 2, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if tool == 'select':
            mode = self.canvas.selection_mode
            if mode == 'rectangle':
                painter.setPen(QPen(white, 2, Qt.PenStyle.DashLine))
                painter.drawRect(5, 6, 24, 22)
            elif mode == 'freehand':
                path = QPainterPath(QPointF(8, 23))
                path.cubicTo(3, 7, 26, 3, 25, 15)
                path.cubicTo(28, 27, 13, 31, 8, 23)
                painter.setPen(QPen(white, 2, Qt.PenStyle.DashLine))
                painter.drawPath(path)
            else:
                painter.setPen(QPen(white, 2, Qt.PenStyle.DashLine))
                painter.drawPolygon(QPolygonF([QPointF(7, 8), QPointF(27, 11),
                                               QPointF(23, 28), QPointF(10, 24)]))
        elif tool == 'brush':
            custom = self.canvas.custom_brushes.get(self.canvas.active_custom_brush)
            if custom is not None:
                painter.drawImage(QRectF(7, 6, 21, 21), custom['tip'])
            elif self.canvas.brush_preset == 'Round':
                painter.setBrush(white); painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(10, 9, 15, 15))
            elif self.canvas.brush_preset == 'Pencil':
                painter.setPen(QPen(white, 1.3))
                for k in range(3):
                    painter.drawLine(6+k*2, 25, 23+k, 7)
            elif self.canvas.brush_preset == 'Ink':
                painter.setPen(QPen(white, 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(8, 25, 26, 9)
            else:
                for radius, alpha in [(13, 40), (10, 65), (7, 110), (4, 180)]:
                    tint = QColor(white); tint.setAlpha(alpha)
                    painter.setBrush(tint); painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(QRectF(17-radius, 17-radius, radius*2, radius*2))
        elif tool == 'eraser':
            radius = max(3, min(12, round(self.canvas.eraser_size / 20) + 3))
            painter.setBrush(QColor('#768799'))
            painter.setPen(QPen(white, 1.6, Qt.PenStyle.DashLine))
            painter.drawEllipse(QRectF(17-radius, 17-radius, radius*2, radius*2))
            painter.setPen(QPen(white, 2))
            painter.drawLine(22, 24, 29, 29)
        painter.end()
        return QIcon(QPixmap.fromImage(img))

    def _refresh_tool_icons(self):
        if not hasattr(self, 'tool_buttons') or not hasattr(self, 'canvas'):
            return
        for tool in ('brush', 'eraser', 'select'):
            button = self.tool_buttons.get(tool)
            if button is None: continue
            button.setText('')
            button.setIcon(self._small_tool_icon(tool))
            button.setIconSize(__import__('PySide6.QtCore', fromlist=['QSize']).QSize(31, 31))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            if tool == 'brush':
                name = self.canvas.custom_brushes.get(self.canvas.active_custom_brush, {}).get('name', self.canvas.brush_preset)
                button.setToolTip(f'Brush: {name} (B; Shift+B cycles)')
            elif tool == 'eraser':
                button.setToolTip(f'Eraser: {self.canvas.eraser_size} px (E)')
            else:
                button.setToolTip(f'Selection: {self.selection_mode_picker.currentText()} (M / L / Shift+L)')

    def _tool_shortcut(self, tool, selection_mode=None):
        """Keyboard tool switch. Text and numeric inputs retain their keys."""
        if not self.project_active or self._shortcut_is_typing():
            return
        if selection_mode is not None:
            self._quick_selection(selection_mode)
        else:
            self.set_tool(tool)
            self.return_canvas_focus()

    def _shortcut_is_typing(self):
        focus = QApplication.focusWidget()
        if focus is None:
            return False
        if isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit,
                              QAbstractSpinBox)):
            return True
        return isinstance(focus, QComboBox) and focus.isEditable()

    def _cycle_brush_preset(self):
        if not self.project_active or self._shortcut_is_typing():
            return
        presets = ['Round', 'Pencil', 'Ink', 'Airbrush']
        current = self.canvas.brush_preset if self.canvas.active_custom_brush is None else None
        index = presets.index(current) if current in presets else -1
        self._quick_brush(presets[(index + 1) % len(presets)])
        self.status.setText('Brush: ' + self.canvas.brush_preset)

    def _cycle_lasso(self):
        if not self.project_active or self._shortcut_is_typing():
            return
        current = self.selection_mode_picker.currentData()
        self._quick_selection('polygonal' if current == 'freehand' else 'freehand')
        self.status.setText('Selection: ' + self.selection_mode_picker.currentText())

    def set_tool(self, tool):
        old_tool = self.canvas.tool
        if old_tool == 'eraser':
            self.canvas.eraser_size = self.canvas.size
        elif old_tool == 'brush':
            self.canvas.brush_settings[self.canvas.brush_preset]['size'] = self.canvas.size
        if tool == 'transform':
            self.canvas.begin_transform(motion=False)
        else:
            self.canvas.cancel_transform()
            self.canvas.change_tool(tool)
        if old_tool != tool and tool in ('brush', 'eraser'):
            size = self.canvas.eraser_size if tool == 'eraser' else self.canvas.brush_settings[self.canvas.brush_preset]['size']
            self.size_input.setValue(size)
        for name, button in self.tool_buttons.items():
            button.setChecked(name == self.canvas.tool)
        self._refresh_tool_icons()
        self.canvas_scroll.tool_changed()

    def adjust_brush(self, offset):
        if QApplication.focusWidget() is self.size_input or QApplication.focusWidget() is self.opacity_input:
            return
        self.size_input.setValue(self.size_input.value() + offset)

    def change_fps(self, fps):
        if self.canvas.playing:
            self.play_start_frame = self.canvas.frame_index
            self.play_clock.restart()
        if self.canvas.fps != fps:
            self.canvas.fps = fps
            self.canvas._mark_dirty()

    def toggle_focus_mode(self):
        if not self.project_active:
            return
        if not self.focus_mode:
            self.focus_restore = {w: w.isVisible() for w in
                (self.top_toolbar, self.settings_scroll, self.right_panel,
                 self.timeline_container, self.timeline_toggle, self.status)}
            for widget in self.focus_restore:
                widget.hide()
            self.focus_mode = True
        else:
            for widget, was_visible in self.focus_restore.items():
                widget.setVisible(was_visible)
            self.focus_restore = {}
            self.focus_mode = False
        self.canvas.setFocus()

    def _exit_focus_mode(self):
        if self.focus_mode:
            self.toggle_focus_mode()

    def _workspace_key(self, panel):
        return f'workspaces/{self.workspace_mode.lower()}/{panel}'

    def _save_workspace_layout(self):
        """Store only explicit panel visibility; not document or animation state."""
        if not self.project_active or self._workspace_restoring or self.focus_mode:
            return
        for panel, widget in (('timeline', self.timeline_container),
                              ('tools', self.settings_scroll),
                              ('layers', self.right_panel)):
            # isHidden measures direct visibility rather than ancestor visibility.
            self.preferences.setValue(self._workspace_key(panel), not widget.isHidden())
        self.preferences.sync()

    def _restore_workspace_layout(self):
        if not self.project_active:
            return
        self._workspace_restoring = True
        try:
            defaults = {'timeline': self.workspace_mode == 'Animation',
                        'tools': False, 'layers': False}
            for panel, widget in (('timeline', self.timeline_container),
                                  ('tools', self.settings_scroll),
                                  ('layers', self.right_panel)):
                shown = self.preferences.value(self._workspace_key(panel),
                                               defaults[panel], type=bool)
                widget.setVisible(shown)
            self.timeline_toggle.setText('Hide Animation Timeline' if not self.timeline_container.isHidden()
                                         else 'Show Animation Timeline')
            self.centralWidget().updateGeometry()
            self.canvas_scroll.viewport().update()
        finally:
            self._workspace_restoring = False

    def _select_workspace(self, name):
        if self.project_active:
            self.workspace_picker.setCurrentText(name)

    def change_workspace(self, name):
        """Switch UI layout only. Never touch canvas project data or playback."""
        if name not in ('Drawing', 'Animation'):
            return
        if name == self.workspace_mode:
            return
        if self.project_active:
            self._exit_focus_mode()
            self._save_workspace_layout()
            # Save the canvas-space point beneath the viewport center. Once Qt
            # recalculates layout sizes, restore that point to preserve panning.
            anchor = self.canvas.mapFrom(self.canvas_scroll.viewport(),
                         self.canvas_scroll.viewport().rect().center())
        else:
            anchor = None
        self.workspace_mode = name
        if self.project_active:
            self._restore_workspace_layout()
            self._workspace_anchor_serial += 1
            serial = self._workspace_anchor_serial
            def restore_pan():
                if serial != self._workspace_anchor_serial or not self.project_active:
                    return
                viewport = self.canvas_scroll.viewport()
                target = self.canvas.mapTo(viewport, anchor)
                midpoint = viewport.rect().center()
                self.canvas_scroll.horizontalScrollBar().setValue(
                    self.canvas_scroll.horizontalScrollBar().value() + target.x() - midpoint.x())
                self.canvas_scroll.verticalScrollBar().setValue(
                    self.canvas_scroll.verticalScrollBar().value() + target.y() - midpoint.y())
            QTimer.singleShot(0, restore_pan)
            self.status.setText(f'{name} workspace: layout changed; drawing and active frame preserved.')
            self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def toggle_timeline(self):
        visible = not self.timeline_container.isVisible()
        self.timeline_container.setVisible(visible)
        self.timeline_toggle.setText('Hide Animation Timeline' if visible else 'Show Animation Timeline')
        self._save_workspace_layout()
        # Widget visibility must not cause the top-level window to grow beyond the screen.
        self.centralWidget().updateGeometry()
        self.canvas_scroll.viewport().update()

    def change_onion_range(self, which, value):
        if which == 'previous':
            self.canvas.onion_previous = value
        else:
            self.canvas.onion_next = value
        if self.project_active:
            self.canvas._mark_dirty()
        self.canvas.update()


    def _timeline_current_changed(self, index):
        if index >= 0:
            self.canvas.change_frame(index)

    def _timeline_selection_changed(self):
        self.timeline_selected_frames = sorted({i.row() for i in self.frame_list.selectedIndexes()})
        self.canvas.multi_edit_frames = list(self.timeline_selected_frames)
        self._refresh_multi_edit_indicator()

    def _refresh_multi_edit_indicator(self):
        if not hasattr(self, 'multi_edit_indicator'):
            return
        enabled = self.multi_edit_checkbox.isChecked()
        count = len(self.timeline_selected_frames)
        if enabled:
            self.multi_edit_indicator.setText(f'MULTI-FRAME EDIT ON ({count} selected)')
            self.multi_edit_indicator.setToolTip('Edits may affect multiple selected cels. Linked cels are edited once.')
            self.multi_edit_indicator.setStyleSheet('QLabel { color: #ffffff; background: #97502d; font-weight: bold; padding: 3px 10px; border: 2px solid #d68a54; border-radius: 4px; }')
        else:
            self.multi_edit_indicator.setText('Single-frame drawing')
            self.multi_edit_indicator.setToolTip('Multi-frame editing is off; only the current frame is changed.')
            self.multi_edit_indicator.setStyleSheet('QLabel { color: #61646a; padding: 3px 10px; border: 1px solid #8a8d92; border-radius: 4px; }')

    def _set_multi_edit(self, checked):
        self.canvas.multi_edit_enabled = bool(checked)
        self.canvas.multi_edit_frames = list(self.timeline_selected_frames)
        self._refresh_multi_edit_indicator()
        self.status.setText('Multi-frame editing enabled for selected frames.' if checked else
                            'Multi-frame editing disabled.')

    def drag_exposure(self, start_index, end_index):
        if end_index <= start_index:
            self.status.setText('To extend an exposure, drag its right edge to a later frame.')
            return
        self._extend_source_through(start_index, end_index)

    def _extend_source_through(self, source_index, end_index):
        if self.canvas.playing or not self.project_active:
            return
        layer = self.canvas.active_layer()
        if layer is None or layer.mode != 'animated':
            QMessageBox.information(self, 'Exposure', 'Select an animated layer.')
            return
        source = next(x for x in self.canvas.frames[source_index] if x.id == layer.id)
        for index in range(source_index + 1, min(end_index + 1, len(self.canvas.frames))):
            target = next(x for x in self.canvas.frames[index] if x.id == layer.id)
            if target.cel_id != source.cel_id and self.canvas._has_pixels(target.image):
                QMessageBox.warning(self, 'Exposure',
                    f'Frame {index + 1} contains independent artwork; nothing was overwritten.')
                return
        def operation():
            while len(self.canvas.frames) <= end_index:
                self.canvas.frames.append(self.canvas._copy_layers(self.canvas.frames[-1], duplicate=False))
            for index in range(source_index + 1, end_index + 1):
                target = next(x for x in self.canvas.frames[index] if x.id == layer.id)
                target.image = source.image
                target.cel_id = source.cel_id
        if self.canvas._edit_timeline(operation):
            self.refresh_frames()
            self.status.setText(f'Exposure: frames {source_index + 1}–{end_index + 1}. Undo is available.')

    def extend_hold_to_frame(self):
        source_index = self.canvas.frame_index
        end, ok = QInputDialog.getInt(self, 'Extend Hold To Frame',
            f'Hold drawing on frame {source_index + 1} through frame:',
            source_index + 2, source_index + 1, 120)
        if ok:
            self._extend_source_through(source_index, end - 1)

    def batch_frame_action(self):
        frames = list(self.timeline_selected_frames)
        if not frames:
            QMessageBox.information(self, 'Batch cels', 'Shift-click or Ctrl-click frame thumbnails to select a range.')
            return
        options = ['Link selected frames from current cel', 'Unlink selected frames', 'Break into independent cels']
        action, ok = QInputDialog.getItem(self, 'Batch Cel Operation',
            f'Operate on {len(frames)} selected frames:', options, 0, False)
        if not ok:
            return
        layer = self.canvas.active_layer()
        if layer is None or layer.mode != 'animated' or self.canvas.playing:
            QMessageBox.warning(self, 'Batch cels', 'Select an animated layer and stop playback first.')
            return
        source_frame = self.canvas.frame_index
        if action == options[0]:
            # No batch operation silently destroys existing independent artwork.
            source = next(x for x in self.canvas.frames[source_frame] if x.id == layer.id)
            for index in frames:
                target = next(x for x in self.canvas.frames[index] if x.id == layer.id)
                if target.cel_id != source.cel_id and self.canvas._has_pixels(target.image):
                    QMessageBox.warning(self, 'Batch cels',
                        f'Frame {index + 1} contains independent artwork. No frames changed.')
                    return
        if action != options[0] and not frames:
            return
        def operation():
            source = next(x for x in self.canvas.frames[source_frame] if x.id == layer.id)
            for index in frames:
                target = next(x for x in self.canvas.frames[index] if x.id == layer.id)
                if action == options[0]:
                    if index != source_frame:
                        target.image = source.image
                        target.cel_id = source.cel_id
                else:
                    target.image = target.image.copy()
                    target.cel_id = uuid.uuid4().hex
        if self.canvas._edit_timeline(operation):
            self.refresh_frames()
            self.status.setText(f'Updated {len(frames)} selected frames (undo available).')

    def _install_shortcuts(self):
        for name, default, callback in self._shortcut_defs:
            sequence = str(self.preferences.value('shortcuts/' + name, default))
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(callback)
            self._shortcut_objects[name] = shortcut

    def show_shortcut_preferences(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Keyboard Shortcuts')
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel('Enter Qt shortcut sequences (e.g. Ctrl+Shift+R). Pan remains Space+drag. Tool letters do not act while typing.'))
        form = QFormLayout()
        from PySide6.QtWidgets import QKeySequenceEdit
        editors = {}
        for name, default, _ in self._shortcut_defs:
            edit = QKeySequenceEdit(self._shortcut_objects[name].key())
            form.addRow(name, edit)
            editors[name] = edit
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        inner = QWidget(); inner.setLayout(form)
        form_scroll.setWidget(inner)
        layout.addWidget(form_scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.RestoreDefaults)
        layout.addWidget(buttons)
        buttons.rejected.connect(dialog.reject)
        def restore():
            for name, default, _ in self._shortcut_defs:
                editors[name].setKeySequence(QKeySequence(default))
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(restore)
        def save():
            sequences = {name: edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText) for name, edit in editors.items()}
            used = {}
            for name, sequence in sequences.items():
                if not sequence:
                    continue
                key = sequence.lower()
                if key in used:
                    QMessageBox.warning(dialog, 'Shortcut conflict', f'{name} conflicts with {used[key]}.')
                    return
                used[key] = name
                if key in ('space', 'shift+space'):
                    QMessageBox.warning(dialog, 'Reserved key', 'Space is reserved for canvas panning.')
                    return
            # File-menu shortcuts remain reserved until unified action routing.
            reserved = {'ctrl+n','ctrl+o','ctrl+s','ctrl+shift+s','ctrl+w','ctrl+i','ctrl+e','ctrl+q'}
            if any(seq.lower() in reserved for seq in sequences.values()):
                QMessageBox.warning(dialog, 'Reserved shortcut', 'This shortcut is used by the File menu.')
                return
            for name, sequence in sequences.items():
                self.preferences.setValue('shortcuts/' + name, sequence)
                self._shortcut_objects[name].setKey(QKeySequence(sequence))
            dialog.accept()
        buttons.accepted.connect(save)
        dialog.resize(450, 520)
        dialog.exec()

    def show_about(self):
        QMessageBox.about(self, 'About Linux Animation Studio',
            f'Linux Animation Studio v{APP_VERSION}\nPython / PySide6\n\n2D drawing and animation development build.')

    def extend_hold(self):
        if not self.canvas.hold_cel(self.hold_length.value()):
            QMessageBox.information(self, 'Exposure hold',
                'Cannot extend: the active track is static, playback is running, or a target frame contains independent artwork. Existing drawings are never overwritten.')

    def split_hold(self):
        if not self.canvas.split_hold():
            QMessageBox.information(self, 'New cel', 'Choose an animated layer and stop playback first.')

    def link_from(self):
        frame, ok = QInputDialog.getInt(self, 'Link cel from frame',
            'Source frame number:', max(1, self.canvas.frame_index), 1, len(self.canvas.frames))
        if ok and not self.canvas.link_cel(frame - 1):
            QMessageBox.information(self, 'Link cel', 'Could not link: select an animated track and a different source cel.')

    def unlink_current(self):
        if not self.canvas.unlink_cel():
            QMessageBox.information(self, 'Unlink cel', 'This cel is not linked to another frame, or playback is running.')

    def refresh_track_visualization(self):
        symbols = {'key':'◆', 'hold':'━', 'link':'↗', 'empty':'·', 'static':'═'}
        rows = []
        for track in self.canvas.layers:
            cells = []
            for index in range(len(self.canvas.frames)):
                kind = self.canvas.cel_kind(track.id, index)
                label = symbols[kind]
                cells.append(f'[{label}]' if index == self.canvas.frame_index else f' {label} ')
            rows.append(f'{track.name[:17]}: ' + ''.join(cells))
        self.track_visualization.setText('   '.join(rows) + '\n◆ key   ━ held   ↗ linked   · empty   ═ static   [ ] playhead')

    def refresh_playhead(self, index):
        self._audio_frame_update(index)
        self.frame_list.blockSignals(True)
        self.frame_list.setCurrentRow(index)
        self.frame_list.blockSignals(False)
        self.frame_label.setText(f'Frame {index + 1} / {len(self.canvas.frames)}')
        self.frame_jump.blockSignals(True)
        self.frame_jump.setRange(1, len(self.canvas.frames))
        self.frame_jump.setValue(index + 1)
        self.frame_jump.blockSignals(False)
        self.refresh_motion()
        self.refresh_track_visualization()

    def refresh_frames(self):
        from PySide6.QtGui import QIcon, QPixmap
        old_selected = list(getattr(self, 'timeline_selected_frames', []))
        self.frame_list.blockSignals(True)
        self.frame_list.clear()
        for index in range(len(self.canvas.frames)):
            item = QListWidgetItem(QIcon(QPixmap.fromImage(self.canvas.frame_thumbnail(index))),
                                   f'Frame {index + 1}')
            self.frame_list.addItem(item)
        self.frame_list.setCurrentRow(self.canvas.frame_index)
        if getattr(self, 'multi_edit_checkbox', None) and self.multi_edit_checkbox.isChecked():
            for selected_index in old_selected:
                if 0 <= selected_index < self.frame_list.count():
                    self.frame_list.item(selected_index).setSelected(True)
            self.timeline_selected_frames = [i for i in old_selected if i < self.frame_list.count()]
        self.canvas.multi_edit_frames = list(self.timeline_selected_frames)
        self._refresh_multi_edit_indicator()
        self.frame_list.blockSignals(False)
        self.frame_label.setText(f'Frame {self.canvas.frame_index + 1} / {len(self.canvas.frames)}')
        self.frame_jump.blockSignals(True)
        self.frame_jump.setRange(1, len(self.canvas.frames))
        self.frame_jump.setValue(self.canvas.frame_index + 1)
        self.frame_jump.blockSignals(False)
        self.fps_input.blockSignals(True)
        self.fps_input.setValue(self.canvas.fps)
        self.fps_input.blockSignals(False)
        self.onion_checkbox.blockSignals(True)
        self.onion_checkbox.setChecked(self.canvas.onion_enabled)
        self.onion_checkbox.blockSignals(False)
        self.onion_spin.blockSignals(True)
        self.onion_spin.setValue(self.canvas.onion_opacity)
        self.onion_spin.blockSignals(False)
        for control, value in ((self.onion_previous_input, self.canvas.onion_previous),
                               (self.onion_next_input, self.canvas.onion_next)):
            control.blockSignals(True)
            control.setValue(value)
            control.blockSignals(False)
        self.loop_checkbox.blockSignals(True)
        self.loop_checkbox.setChecked(getattr(self.canvas, 'loop_playback', True))
        self.loop_checkbox.blockSignals(False)
        self.refresh_motion()
        self.refresh_track_visualization()

    def refresh_title(self):
        if not self.project_active:
            self.setWindowTitle(f'Linux Animation Studio v{APP_VERSION} - No project open')
            return
        name = Path(self.project_path).name if self.project_path else 'Untitled.las'
        self.setWindowTitle(f'Linux Animation Studio v{APP_VERSION} - {name}{" *" if self.canvas.dirty else ""}')

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
        layer = self.canvas.active_layer()
        self.opacity_input.blockSignals(True)
        self.opacity_input.setValue(layer.opacity if layer else 100)
        self.opacity_input.blockSignals(False)
        self.layer_mode.blockSignals(True)
        self.layer_mode.setCurrentIndex(1 if layer and layer.mode == 'static' else 0)
        self.layer_mode.blockSignals(False)

    def change_layer_mode(self, index):
        if not self.project_active or index < 0:
            return
        mode = self.layer_mode.itemData(index)
        layer = self.canvas.active_layer()
        if layer and layer.mode == 'animated' and mode == 'static' and len(self.canvas.frames) > 1:
            answer = QMessageBox.question(self, 'Make static layer?',
                'Use the current frame artwork on ALL frames? Other cels on this layer will be replaced.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                self.refresh_layers()
                return
        self.canvas.set_layer_mode(mode)

    def selection_changed(self, current, previous):
        if current is not None:
            self.canvas.select_layer(current.data(Qt.ItemDataRole.UserRole))
            self.refresh_layers()

    def rename_layer(self):
        layer = self.canvas.active_layer()
        if layer:
            name, ok = QInputDialog.getText(self, 'Rename Layer', 'Name:', text=layer.name)
            if ok:
                self.canvas.rename_layer(name)

    def update_history(self, undo, redo):
        self.undo_button.setEnabled(undo)
        self.redo_button.setEnabled(redo)

    def choose_custom_brush(self, index):
        ident = self.custom_picker.itemData(index)
        self.canvas.active_custom_brush = ident if ident in self.canvas.custom_brushes else None
        if self.canvas.active_custom_brush:
            brush = self.canvas.custom_brushes[ident]
            self.size_input.setValue(brush['size'])
            self.brush_opacity.setValue(brush['opacity'])
            self.spacing_input.blockSignals(True)
            self.spacing_input.setValue(round(brush['spacing'] * 100))
            self.spacing_input.blockSignals(False)
            self.follow_direction.blockSignals(True)
            self.follow_direction.setChecked(brush['follow_direction'])
            self.follow_direction.blockSignals(False)
            for key, widget in self.dynamics_controls.items():
                widget.blockSignals(True)
                widget.setValue(brush[key])
                widget.blockSignals(False)
        self.update_custom_preview()
        self.canvas._stamp_cache.clear()
        self.set_tool('brush')
        self._refresh_tool_icons()

    def change_custom_dynamic(self, key, value):
        ident = self.canvas.active_custom_brush
        if ident in self.canvas.custom_brushes:
            brush = self.canvas.custom_brushes[ident]
            brush[key] = value
            save_custom_brush(ident, brush)
            self.update_custom_preview()

    def update_custom_preview(self):
        ident = self.canvas.active_custom_brush
        if ident not in self.canvas.custom_brushes:
            self.custom_preview.setText('Select a custom brush to preview')
            self.custom_preview.setPixmap(QPixmap())
            return
        brush = self.canvas.custom_brushes[ident]
        preview = QImage(200, 70, IMAGE_FORMAT)
        preview.fill(QColor('#f6f6f6'))
        painter = QPainter(preview)
        original_rng = self.canvas._stamp_rng
        self.canvas._stamp_rng = random.Random(53)
        try:
            for i in range(6):
                self.canvas._paint_custom_stamp(painter, QPointF(23 + i*30, 35), min(38, brush['size']), 0.8, 10.0)
        finally:
            self.canvas._stamp_rng = original_rng
            painter.end()
        self.custom_preview.setPixmap(QPixmap.fromImage(preview))

    def _create_custom_brush(self, image):
        if image.isNull():
            QMessageBox.warning(self, 'Custom brush', 'There are no pixels to use as a brush tip.')
            return
        # Crop transparent padding so a thin tip does not become tiny when scaled.
        bounds = QRect()
        for y in range(image.height()):
            for x in range(image.width()):
                if QColor(image.pixel(x,y)).alpha() > 0:
                    pt = QRect(x,y,1,1)
                    bounds = bounds.united(pt) if not bounds.isNull() else pt
        if bounds.isNull():
            QMessageBox.warning(self, 'Custom brush', 'The selection is transparent.')
            return
        image = image.copy(bounds)
        if max(image.width(), image.height()) > 512:
            image = image.scaled(512,512,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
        name, ok = QInputDialog.getText(self, 'Create Brush', 'Brush name:')
        if not ok or not name.strip(): return
        mode, ok = QInputDialog.getItem(self, 'Brush appearance', 'Stamp style:', ['Preserve original colors', 'Use selected drawing color'], 0, False)
        if not ok: return
        ident = uuid.uuid4().hex
        brush = {'name': name.strip(), 'mode': 'tint' if mode.startswith('Use') else 'color',
                 'spacing': .30, 'size': 48, 'opacity': 100, 'follow_direction': False, 'rotation_jitter': 0, 'scatter': 0, 'pressure_size': 100, 'pressure_opacity': 0, 'tip': image.convertToFormat(IMAGE_FORMAT)}
        try:
            save_custom_brush(ident, brush)
        except OSError as ex:
            QMessageBox.warning(self, 'Custom brush', str(ex)); return
        self.canvas.custom_brushes[ident] = brush
        self.custom_picker.addItem(brush['name'], ident)
        self.custom_picker.setCurrentIndex(self.custom_picker.count()-1)

    def make_custom_brush_from_selection(self):
        layer = self.canvas.active_layer()
        rect = self.canvas.selection
        if layer is None or rect is None or rect.isEmpty():
            QMessageBox.information(self, 'Custom brush', 'Choose a drawing layer and make a selection first.')
            return
        self._create_custom_brush(self.canvas._masked_crop(layer.image, rect))

    def make_custom_brush_from_layer(self):
        layer = self.canvas.active_layer()
        if layer is None: return
        self._create_custom_brush(layer.image.copy())

    def change_custom_spacing(self, value):
        ident = self.canvas.active_custom_brush
        if ident in self.canvas.custom_brushes:
            brush = self.canvas.custom_brushes[ident]
            brush['spacing'] = value / 100.0
            save_custom_brush(ident, brush)
            self.update_custom_preview()

    def delete_custom_brush(self):
        ident = self.canvas.active_custom_brush
        if ident not in self.canvas.custom_brushes: return
        brush = self.canvas.custom_brushes[ident]
        response = QMessageBox.question(self, 'Delete Custom Brush', f'Delete preset "{brush["name"]}"? Existing artwork will stay unchanged.')
        if response != QMessageBox.StandardButton.Yes: return
        for ext in ('.png','.json'):
            (BRUSH_ROOT / (ident + ext)).unlink(missing_ok=True)
        del self.canvas.custom_brushes[ident]
        self.canvas._stamp_cache.clear()
        self.custom_picker.removeItem(self.custom_picker.currentIndex())
        self.custom_picker.setCurrentIndex(0)

    def change_brush_preset(self, name):
        if name not in self.canvas.brush_settings:
            return
        self.canvas.brush_preset = name
        if self.canvas.active_custom_brush is not None:
            self.custom_picker.setCurrentIndex(0)
        settings = self.canvas.brush_settings[name]
        self.size_input.blockSignals(True)
        self.size_input.setValue(self.canvas.eraser_size if self.canvas.tool == 'eraser' else settings['size'])
        self.size_input.blockSignals(False)
        self.brush_opacity.blockSignals(True)
        self.brush_opacity.setValue(settings['opacity'])
        self.brush_opacity.blockSignals(False)
        if self.canvas.tool != 'eraser':
            self.change_size(settings['size'])
        self._refresh_tool_icons()
        self.return_canvas_focus()

    def change_brush_opacity(self, opacity):
        if self.canvas.active_custom_brush in self.canvas.custom_brushes:
            brush = self.canvas.custom_brushes[self.canvas.active_custom_brush]
            brush['opacity'] = opacity
            save_custom_brush(self.canvas.active_custom_brush, brush)
            return
        self.canvas.brush_settings[self.canvas.brush_preset]['opacity'] = opacity

    def change_size(self, size):
        old = self.canvas.cursor_rect()
        self.canvas.size = size
        if self.canvas.tool == 'eraser':
            self.canvas.eraser_size = size
        else:
            self.canvas.brush_settings[self.canvas.brush_preset]['size'] = size
            if self.canvas.active_custom_brush in self.canvas.custom_brushes:
                brush = self.canvas.custom_brushes[self.canvas.active_custom_brush]
                brush['size'] = size
                save_custom_brush(self.canvas.active_custom_brush, brush)
        self.canvas.update()
        self.canvas.refresh_cursor()
        self._refresh_tool_icons()

    def update_color_swatch(self):
        color = self.canvas.color
        self.color_button.setText('●')
        self.color_button.setToolTip(f'Color: {color.name().upper()} (click to change)')
        self.color_button.setStyleSheet(
            f'QPushButton {{ color: {color.name()}; font-size: 27px; '
            'border: 1px solid palette(mid); border-radius: 18px; padding: 0px; }}')

    def adjust_zoom(self, factor):
        if not self.project_active:
            return
        self.canvas.set_zoom(self.canvas.zoom * factor)
        self.status.setText(f'Canvas zoom: {self.canvas.zoom * 100:.0f}%')

    def fit_zoom(self):
        if not self.project_active:
            return
        area = self.canvas_scroll.viewport().size()
        if area.width() <= 0 or area.height() <= 0:
            return
        factor = min((area.width() - 24) / self.canvas.width_px,
                     (area.height() - 24) / self.canvas.height_px)
        self.canvas.set_zoom(max(0.25, min(8.0, factor)))
        self.canvas_scroll.horizontalScrollBar().setValue(0)
        self.canvas_scroll.verticalScrollBar().setValue(0)
        self.status.setText(f'Canvas fitted: {self.canvas.zoom * 100:.0f}%')

    def pick_color(self):
        dialog = ColorStudioDialog(self.canvas.color, self.preferences, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.canvas.color = dialog.current_color()
            self.update_color_swatch()
            self.set_tool('brush')

    def _set_project_active(self, active):
        self._exit_focus_mode()
        if not active and self.project_active:
            self._save_workspace_layout()
        self.project_active = active
        self.workspace.setVisible(active)
        self.welcome.setVisible(not active)
        self.timeline_toggle.setVisible(active)
        self.workspace_picker.setEnabled(active)
        if active:
            # Each workspace remembers its own layout, with Drawing initially
            # timeline-free and Animation initially timeline-visible.
            self._restore_workspace_layout()
        else:
            self.timeline_container.hide()
            self.timeline_toggle.setText('Show Animation Timeline')
        for b in self.toolbar_buttons:
            if b.text() not in ('New', 'Open .las'):
                b.setEnabled(active)
        for b in self.tool_buttons.values():
            b.setEnabled(active)
        self.refresh_title()

    def _confirm_discard(self):
        if not self.project_active or not self.canvas.dirty:
            return True
        answer = QMessageBox.warning(
            self, 'Unsaved project', 'Save changes before continuing?',
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Save)
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Discard:
            return True
        return self.save_project()

    def new_project(self):
        width, ok = QInputDialog.getInt(self, 'New Project', 'Canvas width (px):',
                                        WIDTH, 1, 8192)
        if not ok:
            return
        height, ok = QInputDialog.getInt(self, 'New Project', 'Canvas height (px):',
                                         HEIGHT, 1, 8192)
        if not ok or not self._confirm_discard():
            return
        self.pause_playback()
        self.canvas.reset_document(width, height)
        self.update_color_swatch()
        self._reset_audio()
        self.project_path = None
        self._set_project_active(True)
        self.status.setText('New unsaved project')
        self.canvas.setFocus()

    def close_project(self):
        if not self.project_active or not self._confirm_discard():
            return
        self.pause_playback()
        self.canvas.reset_document()
        self.update_color_swatch()
        self._reset_audio()
        self.project_path = None
        self._set_project_active(False)
        self.status.setText('No project open')

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open editable project',
                                              str(Path.home()), 'LAS projects (*.las)')
        if not path or not self._confirm_discard():
            return
        self.pause_playback()
        try:
            self.canvas.load_project(path)
            self.update_color_swatch()
            self._reload_audio()
            self.project_path = path
            self._set_project_active(True)
            self.status.setText(f'Opened: {path}')
        except Exception as exc:
            QMessageBox.critical(self, 'Open failed', str(exc))

    def save_project_as(self):
        if not self.project_active:
            return False
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
        if not self.project_active:
            return False
        return self._save_to(self.project_path) if self.project_path else self.save_project_as()

    def _reset_audio(self):
        self.audio_player.stop()
        self.audio_player.setSource(QUrl())
        self.canvas.audio_bytes = None
        self.canvas.audio_name = ''
        self.canvas.audio_suffix = ''
        self.audio_wave.peaks = []
        self.audio_wave.position = 0
        self.audio_wave.update()
        self.audio_label.setText('No audio imported')

    def _reload_audio(self):
        self.audio_player.stop()
        self.audio_player.setSource(QUrl())
        data = getattr(self.canvas, 'audio_bytes', None)
        if not data:
            self.audio_wave.peaks = []
            self.audio_label.setText('No audio imported')
        else:
            suffix = self.canvas.audio_suffix
            file = Path(self.audio_temp.name) / ('imported_audio' + suffix)
            file.write_bytes(data)
            self.audio_player.setSource(QUrl.fromLocalFile(str(file)))
            self.audio_wave.peaks = audio_waveform(data, suffix)
            self.audio_label.setText(self.canvas.audio_name)
        self.audio_wave.update()

    def import_audio(self):
        if not self.project_active:
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Import timeline audio',
            str(Path.home()), 'Audio (*.wav *.mp3)')
        if not path:
            return
        try:
            file = Path(path)
            if file.suffix.lower() not in ('.wav', '.mp3'):
                raise ValueError('Only WAV and MP3 supported')
            if file.stat().st_size > 80 * 1024 * 1024:
                raise ValueError('Audio must be less than 80 MB')
            data = file.read_bytes()
            if not data:
                raise ValueError('Audio file is empty')
            self.pause_playback()
            self.canvas.audio_bytes = data
            self.canvas.audio_name = file.name
            self.canvas.audio_suffix = file.suffix.lower()
            self._reload_audio()
            self.canvas._mark_dirty()
        except Exception as exc:
            QMessageBox.critical(self, 'Audio import failed', str(exc))

    def remove_audio(self):
        if getattr(self.canvas, 'audio_bytes', None):
            self.pause_playback()
            self._reset_audio()
            self.canvas._mark_dirty()

    def set_audio_mute(self, checked):
        self.audio_output.setMuted(bool(checked))

    def seek_audio_fraction(self, fraction):
        count = len(self.canvas.frames)
        frame = min(count-1, round(fraction * count))
        self.canvas.change_frame(frame)

    def _audio_frame_update(self, index):
        self.audio_wave.position = index / max(1, len(self.canvas.frames) - 1)
        self.audio_wave.update()
        if not self.canvas.playing and getattr(self.canvas, 'audio_bytes', None):
            self.audio_player.setPosition(round(index * 1000 / self.canvas.fps))

    def import_image_layer(self):
        if not self.project_active:
            QMessageBox.information(self, 'Import', 'Create or open a project first.')
            return
        if self.canvas.playing:
            self.pause_playback()
        path, _ = QFileDialog.getOpenFileName(self, 'Import image as layer', '',
                                              'Images (*.png *.jpg *.jpeg *.webp)')
        if not path:
            return
        source = QImage(path)
        if source.isNull():
            QMessageBox.warning(self, 'Import image', 'Unable to decode the selected image.')
            return
        w, h = self.canvas.width_px, self.canvas.height_px
        if source.width() > w or source.height() > h:
            answer = QMessageBox.question(self, 'Image is larger than canvas',
                'Scale the image to fit the canvas? Choose No to keep its original size and crop overflow.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Yes:
                source = source.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        new_image = transparent_image(w, h)
        painter = QPainter(new_image)
        painter.drawImage((w - source.width()) // 2, (h - source.height()) // 2, source)
        painter.end()
        layer = self.canvas.active_layer()
        idx = self.canvas.layers.index(layer) + 1 if layer else len(self.canvas.layers)
        name = '[Reference] ' + (Path(path).stem[:60] or 'Imported image')
        imported = Layer(uuid.uuid4().hex, name, new_image)
        cmd = dict(type='add', layer=imported, index=idx, previous_active=self.canvas.active_id)
        self.canvas._apply(cmd, True)
        self.canvas._push(cmd)
        self.refresh_layers()

    def export_png(self):
        if not self.project_active:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Export visible layers as PNG',
                                               str(Path.home()/'drawing.png'), 'PNG files (*.png)')
        if not path:
            return
        if not path.lower().endswith('.png'):
            path += '.png'
        ok = self.canvas.composite(True).save(path, 'PNG')
        self.status.setText(('Exported: ' if ok else 'Export failed: ') + path)

    def export_animation(self):
        if not self.project_active:
            return
        self.pause_playback()
        dialog = QDialog(self)
        dialog.setWindowTitle('Export Animation')
        form = QFormLayout(dialog)
        fmt = QComboBox()
        fmt.addItems(['PNG sequence (transparent)', 'PNG sequence (white background)', 'MP4 (H.264)'])
        form.addRow('Output:', fmt)
        fps = QSpinBox()
        fps.setRange(1, 60)
        fps.setValue(self.canvas.fps)
        form.addRow('Export FPS:', fps)
        quality = QComboBox()
        quality.addItems(['High', 'Balanced', 'Small file'])
        form.addRow('MP4 quality:', quality)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        is_mp4 = fmt.currentIndex() == 2
        if is_mp4 and not resolve_ffmpeg():
            QMessageBox.warning(self, 'FFmpeg missing',
                                'FFmpeg was not found. Install FFmpeg and add it to PATH, or set LAS_FFMPEG_PATH to its executable.')
            return
        if is_mp4:
            destination, _ = QFileDialog.getSaveFileName(
                self, 'Export MP4', str(Path.home() / 'animation.mp4'), 'MP4 Video (*.mp4)')
            if not destination:
                return
            if not destination.lower().endswith('.mp4'):
                destination += '.mp4'
        else:
            destination = QFileDialog.getExistingDirectory(self, 'Choose PNG sequence folder',
                                                            str(Path.home()))
            if not destination:
                return
            destination = str(Path(destination) / 'animation_frames')
            if Path(destination).exists() and any(Path(destination).iterdir()):
                if QMessageBox.question(self, 'Overwrite frames?',
                    'The animation_frames folder is not empty. Replace existing numbered PNGs?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                    return
        output_fps = fps.value()
        source_fps = self.canvas.fps
        source_count = len(self.canvas.frames)
        output_count = max(1, math.ceil(source_count * output_fps / source_fps))
        progress = QProgressDialog('Rendering frames...', 'Cancel', 0, output_count, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        try:
            with tempfile.TemporaryDirectory(prefix='las-export-') as temp:
                folder = Path(temp) if is_mp4 else Path(destination)
                folder.mkdir(parents=True, exist_ok=True)
                for i in range(output_count):
                    QApplication.processEvents()
                    if progress.wasCanceled():
                        self.status.setText('Export canceled')
                        return
                    source_index = min(source_count - 1, i * source_fps // output_fps)
                    bg = 'white' if is_mp4 or fmt.currentIndex() == 1 else None
                    frame = self.canvas.render_frame(source_index, bg)
                    if is_mp4 and (frame.width() % 2 or frame.height() % 2):
                        padded = QImage(frame.width() + frame.width() % 2,
                                        frame.height() + frame.height() % 2, IMAGE_FORMAT)
                        padded.fill(Qt.GlobalColor.white)
                        painter = QPainter(padded)
                        painter.drawImage(0, 0, frame)
                        painter.end()
                        frame = padded
                    name = folder / f'frame_{i+1:06d}.png'
                    if not frame.save(str(name), 'PNG'):
                        raise OSError(f'Could not write {name}')
                    progress.setValue(i + 1)
                if is_mp4:
                    progress.setLabelText('Encoding MP4 with FFmpeg...')
                    progress.setRange(0, 0)
                    crf = [18, 23, 28][quality.currentIndex()]
                    command = [resolve_ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y',
                               '-framerate', str(output_fps), '-i', str(folder / 'frame_%06d.png')]
                    if getattr(self.canvas, 'audio_bytes', None):
                        audio_path = folder / ('audio_input' + self.canvas.audio_suffix)
                        audio_path.write_bytes(self.canvas.audio_bytes)
                        command += ['-i', str(audio_path)]
                    command += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', str(crf)]
                    if getattr(self.canvas, 'audio_bytes', None):
                        command += ['-c:a', 'aac', '-b:a', '192k', '-af', 'apad', '-shortest']
                    command += ['-movflags', '+faststart', destination]
                    process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                                               stderr=subprocess.PIPE)
                    while process.poll() is None:
                        QApplication.processEvents()
                        if progress.wasCanceled():
                            process.kill()
                            process.communicate()
                            Path(destination).unlink(missing_ok=True)
                            self.status.setText('MP4 export canceled')
                            return
                        import time
                        time.sleep(0.03)
                    error = process.communicate()[1].decode('utf-8', 'replace')
                    if process.returncode:
                        Path(destination).unlink(missing_ok=True)
                        raise RuntimeError(error[-2500:] or 'FFmpeg encoding failed')
            self.status.setText(f'Exported: {destination}')
            QMessageBox.information(self, 'Export complete', f'Saved to:\n{destination}')
        except Exception as exc:
            QMessageBox.critical(self, 'Animation export failed', str(exc))
        finally:
            progress.close()

    def closeEvent(self, event):
        self.pause_playback()
        if self._confirm_discard():
            if self.focus_mode:
                self._exit_focus_mode()
            self._save_workspace_layout()
            self.audio_temp.cleanup()
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    QCoreApplication.setOrganizationName('LinuxAnimationStudio')
    QCoreApplication.setApplicationName('LinuxAnimationStudio')
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
