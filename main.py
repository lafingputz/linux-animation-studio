"""Linux Animation Studio v0.16: custom brush dynamics and preview."""
import io
import os
import math
import random
import shutil
import subprocess
import tempfile
import json
import sys
import uuid
import zipfile
from dataclasses import dataclass
from bisect import bisect_left
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QTimer, QElapsedTimer, Qt, Signal
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QPen, QShortcut, QRadialGradient, QTransform, QPixmap
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QColorDialog, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget, QInputDialog, QSpinBox, QDoubleSpinBox, QToolButton, QButtonGroup, QFrame, QCheckBox, QProgressDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
)

WIDTH, HEIGHT = 1200, 800
IMAGE_FORMAT = QImage.Format.Format_ARGB32_Premultiplied
PROJECT_VERSION = 4
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


BRUSH_ROOT = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))) / 'linux-animation-studio' / 'brushes'


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
                              'spacing': max(0.05, min(4.0, float(meta.get('spacing', .30)))),
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
        self.color = QColor('#222222')
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
        self.selection = None  # QRect in document pixels
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
                ghost.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                ghost.fillRect(self.move_source_rect, Qt.GlobalColor.transparent)
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
            for index, tint in ((self.frame_index - 1, QColor('#d65c66')),
                                (self.frame_index + 1, QColor('#35a87c'))):
                neighbor = self._tinted_neighbor(index, tint)
                if neighbor is not None:
                    p.setOpacity(self.onion_opacity / 100.0)
                    p.drawImage(0, 0, neighbor)
            p.setOpacity(1.0)
        outlined = None if self.playing else (self.drag_rect if self.drag_rect is not None else self.selection)
        if outlined is not None and not outlined.isEmpty():
            p.setPen(QPen(QColor(255,255,255), 1, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(outlined)
            p.setPen(QPen(QColor(10,10,10), 1, Qt.PenStyle.DotLine))
            p.drawRect(outlined.adjusted(1,1,-1,-1))
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
                source=layer.image.copy(), offset=QPointF(0, 0), scale=1.0, angle=0.0)
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
        painter = QPainter(image)
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

    def apply_transform(self):
        session=self.transform_session
        if session is None:return
        if session['kind']=='raster':
            layer=self.layer_by_id(session['id'])
            if layer is not None:
                before=session['source']
                after=self._transformed_layer_image(session)
                if before!=after:
                    layer.image=after
                    self._push(dict(type='patch',id=layer.id,frame=session['frame'],rect=after.rect(),before=before,after=after.copy()))
        else:
            obj=self.active_motion()
            if obj and obj.id==session['id']:
                values=session['values']
                self.set_motion_key(*values)
        self.cancel_transform()
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
        width = self.size * (0.15 + 0.85 * pressure) if tablet else self.size
        self._include_point(point, width)
        if self.last is not None:
            self._include_point(self.last, self.size)
        painter = QPainter(layer.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.selection is not None:
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
        if layer is not None and self._before_stroke is not None and not self._stroke_bounds.isNull():
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

    def set_selection(self, rect):
        self.selection = rect.intersected(QRect(0, 0, self.width_px, self.height_px)) if rect else None
        if self.selection is not None and self.selection.isEmpty():
            self.selection = None
        self.update()

    def select_all(self):
        self.set_selection(QRect(0, 0, self.width_px, self.height_px))

    def deselect(self):
        self.set_selection(None)

    def keyPressEvent(self, event):
        if self.transform_session is not None:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.apply_transform()
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
            self.drag_origin = point
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
            self.move_source = layer.image.copy(self.move_source_rect)
            self.move_preview = QRect(self.move_source_rect)
            self.move_offset = QPoint(0, 0)
            self.update()

    def _update_interaction(self, position):
        if self.tool == 'transform' and self.transform_drag is not None:
            self._transform_move(QPointF(position))
            return
        if self.drag_origin is None:
            return
        point = self._point(position)
        if self.tool == 'select':
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
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                painter.fillRect(source, Qt.GlobalColor.transparent)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                painter.drawImage(destination.topLeft(), self.move_source)
                painter.end()
                after = layer.image.copy(affected)
                if before != after:
                    self._push(dict(type='patch', id=layer.id, rect=affected,
                                    before=before, after=after))
                if self.selection is not None:
                    self.selection = destination.intersected(layer.image.rect())
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
        layer.image = after
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
                      x.visible, x.opacity, x.mode) for x in layers]

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
        for frame in self.frames:
            layer = next(x for x in frame if x.id == target.id)
            layer.mode = mode
            layer.image = shared if mode == 'static' else shared.copy() if frame is self.frames[self.frame_index] else layer.image.copy()
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
                result.append(Layer(track.id, track.name, image, track.visible, track.opacity, track.mode))
            frame[:] = result
        self.layers = self.frames[self.frame_index]


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
        self.cancel_transform()
        self.drawing = False
        self.drag_origin = None
        self.drag_rect = None
        self.move_source = None
        self.move_preview = None
        self.selection = None
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
        self.loop_playback = True
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
                        loop_playback=getattr(self, 'loop_playback', True), frames=[], motion_objects=[])
        path = Path(path)
        temporary = path.with_name(path.name + '.tmp')
        try:
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for index, layers in enumerate(self.frames):
                    records = []
                    for layer in layers:
                        filename = f'frames/{index}/{layer.id}.png'
                        records.append(dict(id=layer.id, name=layer.name, visible=layer.visible,
                                            opacity=layer.opacity, mode=layer.mode, file=filename))
                        archive.writestr(filename, png_bytes(layer.image))
                    manifest['frames'].append(dict(layers=records))
                for obj in self.motion_objects:
                    filename = f'motion/{obj.id}.png'
                    archive.writestr(filename, png_bytes(obj.image))
                    manifest['motion_objects'].append(dict(id=obj.id, name=obj.name, file=filename,
                        keys={str(k): list(v) for k, v in obj.keys.items()}))
                manifest['active_motion_id'] = self.active_motion_id
                manifest['active_layer'] = self.active_id
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
            if info.get('format') != 'linux-animation-studio' or version not in (1, 2, 3, 4):
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
                                        bool(entry['visible']), opacity, entry.get('mode', 'animated') if version >= 4 else 'animated'))
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
                    template.visible, template.opacity, template.mode) for template in definitions])
            frames = aligned
            for track_index, template in enumerate(definitions):
                if template.mode == 'static':
                    shared = frames[0][track_index].image
                    for frame in frames:
                        frame[track_index].image = shared
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
            active_id = info.get('active_layer')
            if not any(layer.id == active_id for layer in frames[index]):
                active_id = frames[index][-1].id
        self.deselect()
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
        self.loop_playback = bool(info.get('loop_playback', True))
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project_path = None
        self.project_active = True
        self.resize(1370, 930)
        self.play_timer = QTimer(self)
        self.play_timer.setInterval(15)
        self.play_timer.timeout.connect(self._playback_tick)
        self.play_clock = QElapsedTimer()
        self.play_start_frame = 0
        self._refreshing_frames = False
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

        self.color_button = button('Color', self.pick_color)
        self.update_color_swatch()
        self.undo_button = button('Undo', self.canvas.undo)
        self.redo_button = button('Redo', self.canvas.redo)
        self.undo_button.setEnabled(False)
        self.redo_button.setEnabled(False)
        self.canvas.history_changed.connect(self.update_history)
        button('Clear Layer', self.canvas.clear)
        button('Deselect', self.canvas.deselect)
        button('New', self.new_project)
        button('Open .las', self.open_project)
        button('Close', self.close_project)
        button('Save .las', self.save_project)
        button('Export PNG', self.export_png)
        vertical.addLayout(toolbar)

        content = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel('TOOLS'))
        self.tool_buttons = {}
        for tool, text in [('brush','Brush'), ('eraser','Eraser'),
                           ('select','Rectangle Select'), ('move','Move Pixels'), ('transform','Transform')]:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setMinimumWidth(130)
            b.clicked.connect(lambda checked, t=tool: self.set_tool(t))
            self.tool_buttons[tool] = b
            left.addWidget(b)
        self.tool_buttons['brush'].setChecked(True)
        transform_buttons = QHBoxLayout()
        apply_button = QPushButton('Apply Transform')
        apply_button.clicked.connect(self.canvas.apply_transform)
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
        self.spacing_input.setRange(5, 400)
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
        content.addLayout(left)

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
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
        content.addLayout(right)
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

        self.timeline_container = QWidget()
        timeline = QVBoxLayout(self.timeline_container)
        frame_controls = QHBoxLayout()
        for label, func in [('Previous', lambda: self.canvas.change_frame(self.canvas.frame_index-1)),
                            ('Next', lambda: self.canvas.change_frame(self.canvas.frame_index+1)),
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
        frame_controls.addStretch()
        timeline.addLayout(frame_controls)
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
        timeline.addLayout(motion_controls)
        self.canvas.motion_changed.connect(self.refresh_motion)
        self.frame_list = QListWidget()
        self.frame_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.frame_list.setFlow(QListWidget.Flow.LeftToRight)
        self.frame_list.setWrapping(False)
        self.frame_list.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(90,60))
        self.frame_list.setFixedHeight(108)
        self.frame_list.setSpacing(5)
        self.frame_list.currentRowChanged.connect(self.canvas.change_frame)
        timeline.addWidget(self.frame_list)
        self.timeline_toggle = QPushButton('Hide Animation Timeline')
        self.timeline_toggle.clicked.connect(self.toggle_timeline)
        vertical.addWidget(self.timeline_toggle)
        vertical.addWidget(self.timeline_container)
        vertical.addWidget(self.status)
        self.setCentralWidget(root)
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
        self._set_project_active(True)
        for seq, fn in [('Ctrl+Z', self.canvas.undo), ('Ctrl+Shift+Z', self.canvas.redo),
                        ('Ctrl+Y', self.canvas.redo),
                        ('[', lambda: self.adjust_brush(-1)),
                        (']', lambda: self.adjust_brush(1)),
                        ('Ctrl+A', self.canvas.select_all), ('Ctrl+D', self.canvas.deselect),
                        ('Alt+Left', lambda: self.navigate_frame(-1)),
                        ('Alt+Right', lambda: self.navigate_frame(1)),
                        (',', lambda: self.navigate_frame(-1)),
                        ('.', lambda: self.navigate_frame(1)),
                        ('Space', self.toggle_playback),
                        ('Ctrl++', lambda: self.adjust_zoom(1.25)),
                        ('Ctrl+=', lambda: self.adjust_zoom(1.25)),
                        ('Ctrl+-', lambda: self.adjust_zoom(0.8)),
                        ('Ctrl+0', self.fit_zoom)]:
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
        self.play_start_frame = self.canvas.frame_index
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
        if index != self.canvas.frame_index:
            self.canvas.change_frame(index, playback=True)

    def pause_playback(self):
        self.play_timer.stop()
        self.canvas.playing = False
        self.play_button.setText('▶ Play')
        self.canvas.update()

    def stop_playback(self):
        self.pause_playback()
        self.canvas.change_frame(0, playback=True)

    def activate_motion_transform(self):
        if self.canvas.begin_transform(motion=True):
            for name, button in self.tool_buttons.items():
                button.setChecked(name == 'transform')
            self.return_canvas_focus()

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

    def toggle_timeline(self):
        visible = not self.timeline_container.isVisible()
        self.timeline_container.setVisible(visible)
        self.timeline_toggle.setText('Hide Animation Timeline' if visible else 'Show Animation Timeline')

    def refresh_playhead(self, index):
        self.frame_list.blockSignals(True)
        self.frame_list.setCurrentRow(index)
        self.frame_list.blockSignals(False)
        self.frame_label.setText(f'Frame {index + 1} / {len(self.canvas.frames)}')
        self.refresh_motion()

    def refresh_frames(self):
        from PySide6.QtGui import QIcon, QPixmap
        self.frame_list.blockSignals(True)
        self.frame_list.clear()
        for index in range(len(self.canvas.frames)):
            item = QListWidgetItem(QIcon(QPixmap.fromImage(self.canvas.frame_thumbnail(index))),
                                   f'Frame {index + 1}')
            self.frame_list.addItem(item)
        self.frame_list.setCurrentRow(self.canvas.frame_index)
        self.frame_list.blockSignals(False)
        self.frame_label.setText(f'Frame {self.canvas.frame_index + 1} / {len(self.canvas.frames)}')
        self.fps_input.blockSignals(True)
        self.fps_input.setValue(self.canvas.fps)
        self.fps_input.blockSignals(False)
        self.onion_checkbox.blockSignals(True)
        self.onion_checkbox.setChecked(self.canvas.onion_enabled)
        self.onion_checkbox.blockSignals(False)
        self.onion_spin.blockSignals(True)
        self.onion_spin.setValue(self.canvas.onion_opacity)
        self.onion_spin.blockSignals(False)
        self.loop_checkbox.blockSignals(True)
        self.loop_checkbox.setChecked(getattr(self.canvas, 'loop_playback', True))
        self.loop_checkbox.blockSignals(False)
        self.refresh_motion()

    def refresh_title(self):
        if not self.project_active:
            self.setWindowTitle('Linux Animation Studio v0.13 - No project open')
            return
        name = Path(self.project_path).name if self.project_path else 'Untitled.las'
        self.setWindowTitle(f'Linux Animation Studio v0.13 - {name}{" *" if self.canvas.dirty else ""}')

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
            QMessageBox.information(self, 'Custom brush', 'Choose a drawing layer and make a rectangle selection first.')
            return
        self._create_custom_brush(layer.image.copy(rect))

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

    def update_color_swatch(self):
        color = self.canvas.color
        ink = '#ffffff' if color.lightness() < 130 else '#111111'
        self.color_button.setText('Color  ' + color.name().upper())
        self.color_button.setStyleSheet(f'QPushButton {{ background-color: {color.name()}; color: {ink}; border: 1px solid #888; padding: 5px; }}')

    def adjust_zoom(self, factor):
        if not self.project_active:
            return
        self.canvas.set_zoom(self.canvas.zoom * factor)
        self.status.setText(f'Canvas zoom: {self.canvas.zoom * 100:.0f}%')

    def fit_zoom(self):
        if self.project_active:
            self.canvas.set_zoom(1.0)

    def pick_color(self):
        color = QColorDialog.getColor(self.canvas.color, self, 'Choose brush color')
        if color.isValid():
            self.canvas.color = color
            self.update_color_swatch()
            self.set_tool('brush')

    def _set_project_active(self, active):
        self.project_active = active
        self.workspace.setVisible(active)
        self.welcome.setVisible(not active)
        self.timeline_toggle.setVisible(active)
        self.timeline_container.setVisible(active)
        for b in self.toolbar_buttons:
            if b.text() not in ('New', 'Open .las'):
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
        self.project_path = None
        self._set_project_active(True)
        self.status.setText('New unsaved project')
        self.canvas.setFocus()

    def close_project(self):
        if not self.project_active or not self._confirm_discard():
            return
        self.pause_playback()
        self.canvas.reset_document()
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
        if is_mp4 and not shutil.which('ffmpeg'):
            QMessageBox.warning(self, 'FFmpeg missing',
                                'Install FFmpeg with: sudo apt install ffmpeg')
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
                    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                               '-framerate', str(output_fps), '-i', str(folder / 'frame_%06d.png'),
                               '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', str(crf),
                               '-movflags', '+faststart', destination]
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
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
