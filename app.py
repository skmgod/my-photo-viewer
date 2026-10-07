"""내 사진 뷰어 - 알씨 스타일 이미지 뷰어 + AI 도구 (PySide6)"""
import os
import re
import sys
import time
import traceback

import numpy as np
from PySide6.QtCore import (QFile, QFileInfo, QObject, QPointF, QRectF, QRunnable, QSize, Qt,
                            QThreadPool, QTimer, Signal)
from PySide6.QtGui import (QAction, QBrush, QColor, QFont, QFontDatabase, QIcon, QImage,
                           QImageReader, QKeySequence, QPainter, QPainterPath, QPen, QPixmap,
                           QTransform)
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QGraphicsEllipseItem,
                               QGraphicsPathItem, QGraphicsPixmapItem, QGraphicsRectItem,
                               QGraphicsScene, QGraphicsView, QHBoxLayout, QInputDialog, QLabel,
                               QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QProgressDialog, QPushButton, QSlider, QToolBar,
                               QToolButton, QVBoxLayout, QWidget, QDockWidget)

import ctypes
from ctypes import wintypes

from PySide6.QtPrintSupport import QPrintDialog, QPrinter

import ai_tools

APP_NAME = "내 사진 뷰어"
EXTS = {bytes(f).decode().lower() for f in QImageReader.supportedImageFormats()}


# ------------------------------------------------------------------ 변환 도우미
def qimage_to_bgra(img):
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    w, h = img.width(), img.height()
    arr = np.frombuffer(img.constBits(), np.uint8).reshape(h, img.bytesPerLine() // 4, 4)[:, :w]
    return arr.copy()


def bgra_to_qimage(arr):
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    return QImage(arr.data, w, h, w * 4, QImage.Format.Format_ARGB32).copy()


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


# ------------------------------------------------------------------ 아이콘
def _icon_font():
    fams = QFontDatabase.families()
    for name in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
        if name in fams:
            return name
    return None


ICON_FONT = None


def make_icon(draw, size=32):
    icon = QIcon()
    for mode, color in ((QIcon.Mode.Normal, QColor("#3a3a3a")), (QIcon.Mode.Disabled, QColor("#c4c4c4"))):
        pm = QPixmap(size * 2, size * 2)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        p.scale(2, 2)
        draw(p, size, color)
        p.end()
        pm.setDevicePixelRatio(2)
        icon.addPixmap(pm, mode)
    return icon


def glyph(code, fallback=""):
    def draw(p, s, color):
        p.setPen(color)
        if ICON_FONT:
            f = QFont(ICON_FONT)
            f.setPixelSize(int(s * 0.78))
            p.setFont(f)
            p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, chr(code))
        else:
            f = QFont("Malgun Gothic")
            f.setPixelSize(int(s * 0.5))
            p.setFont(f)
            p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, fallback)
    return make_icon(draw)


def draw_ai(p, s, color):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#a23be8"))
    p.drawRoundedRect(QRectF(3, 3, s - 6, s - 6), 7, 7)
    f = QFont("Segoe UI")
    f.setBold(True)
    f.setPixelSize(int(s * 0.5))
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(QRectF(3, 3, s - 6, s - 6), Qt.AlignmentFlag.AlignCenter, "Ai")


def draw_one(p, s, color):
    pen = QPen(color, 1.8)
    p.setPen(pen)
    p.drawRoundedRect(QRectF(5, 5, s - 10, s - 10), 2, 2)
    f = QFont("Segoe UI")
    f.setBold(True)
    f.setPixelSize(int(s * 0.3))
    p.setFont(f)
    p.drawText(QRectF(5, 5, s - 10, s - 10), Qt.AlignmentFlag.AlignCenter, "1:1")


def draw_fit(p, s, color):
    p.setPen(QPen(color, 1.8))
    a, b, L = 5, s - 5, 7
    for (x, y, dx, dy) in ((a, a, 1, 1), (b, a, -1, 1), (a, b, 1, -1), (b, b, -1, -1)):
        p.drawLine(QPointF(x, y), QPointF(x + dx * L, y))
        p.drawLine(QPointF(x, y), QPointF(x, y + dy * L))
    p.drawRect(QRectF(11, 11, s - 22, s - 22))


# ------------------------------------------------------------------ 백그라운드 작업
class _Signals(QObject):
    done = Signal(object)
    fail = Signal(str)
    prog = Signal(int)


class Task(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = _Signals()
        self.setAutoDelete(False)

    def run(self):
        try:
            self.signals.done.emit(self.fn(self.signals.prog.emit))
        except Exception as e:  # noqa
            traceback.print_exc()
            self.signals.fail.emit(str(e) or e.__class__.__name__)


# ------------------------------------------------------------------ 뷰어
class Viewer(QGraphicsView):
    zoomChanged = Signal(float)
    hoverPixel = Signal(int, int)
    contextRequested = Signal(object)

    def __init__(self):
        super().__init__()
        self.sc = QGraphicsScene(self)
        self.setScene(self.sc)
        self.setBackgroundBrush(QColor(0, 0, 0))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.item = None
        self.checker = None
        self.fit_mode = "shrink"
        self.smooth = True
        self.zoom = 1.0
        self.img_size = QSize(0, 0)
        # 지우개
        self.erasing = False
        self.brush = 40
        self.strokes = []  # (QPainterPath, size)
        self._cur = None
        self._cur_item = None
        self._cursor_item = None

    # --- 이미지
    def set_image(self, img, keep_view=False, checker=False):
        old = (self.zoom, self.fit_mode, self.horizontalScrollBar().value(),
               self.verticalScrollBar().value())
        self.end_erase()
        self.sc.clear()
        self.img_size = img.size()
        self.checker = None
        if checker:
            tile = QPixmap(16, 16)
            tile.fill(QColor("#ffffff"))
            qp = QPainter(tile)
            qp.fillRect(0, 0, 8, 8, QColor("#cccccc"))
            qp.fillRect(8, 8, 8, 8, QColor("#cccccc"))
            qp.end()
            self.checker = QGraphicsRectItem(QRectF(0, 0, img.width(), img.height()))
            self.checker.setBrush(QBrush(tile))
            self.checker.setPen(QPen(Qt.PenStyle.NoPen))
            self.sc.addItem(self.checker)
        self.item = QGraphicsPixmapItem(QPixmap.fromImage(img))
        self.sc.addItem(self.item)
        self.sc.setSceneRect(QRectF(0, 0, img.width(), img.height()))
        if keep_view and old[1] is None:
            self.set_zoom(old[0])
            self.horizontalScrollBar().setValue(old[2])
            self.verticalScrollBar().setValue(old[3])
        elif keep_view:
            self.fit(old[1] == "fit")
        else:
            self.fit(False)

    def clear(self):
        self.end_erase()
        self.sc.clear()
        self.item = None
        self.img_size = QSize(0, 0)

    def set_zoom(self, z, manual=False):
        z = max(0.02, min(32.0, z))
        self.resetTransform()
        self.scale(z, z)
        self.zoom = z
        if manual:
            self.fit_mode = None
        if self.item:
            self.apply_smooth()
        self.zoomChanged.emit(z)

    def apply_smooth(self):
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self.smooth)
        if self.item:
            self.item.setTransformationMode(Qt.TransformationMode.SmoothTransformation if self.smooth
                                            else Qt.TransformationMode.FastTransformation)

    def contextMenuEvent(self, e):
        self.contextRequested.emit(e.globalPos())

    def fit(self, enlarge=False):
        if not self.item:
            return
        vw, vh = self.viewport().width(), self.viewport().height()
        z = min(vw / self.img_size.width(), vh / self.img_size.height())
        if not enlarge:
            z = min(z, 1.0)
        self.fit_mode = "fit" if enlarge else "shrink"
        self.set_zoom(z)

    def zoom_by(self, factor):
        if self.item:
            self.set_zoom(self.zoom * factor, manual=True)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.fit_mode and self.item:
            self.fit(self.fit_mode == "fit")

    def wheelEvent(self, e):
        self.zoom_by(1.15 ** (e.angleDelta().y() / 120))

    def mouseDoubleClickEvent(self, e):
        if self.erasing:
            return
        if self.fit_mode:
            self.set_zoom(1.0, manual=True)
        else:
            self.fit(False)

    # --- 지우개
    def begin_erase(self, size):
        self.erasing = True
        self.brush = size
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self._cursor_item = QGraphicsEllipseItem(0, 0, size, size)
        self._cursor_item.setPen(QPen(QColor("white"), 0))
        self._cursor_item.setZValue(10)
        self._cursor_item.hide()
        self.sc.addItem(self._cursor_item)

    def end_erase(self):
        self.erasing = False
        self.strokes = []
        self._cur = self._cur_item = None
        if self._cursor_item is not None:
            try:
                self.sc.removeItem(self._cursor_item)
            except RuntimeError:
                pass
            self._cursor_item = None
        if hasattr(self, "_stroke_items"):
            for it in self._stroke_items:
                try:
                    self.sc.removeItem(it)
                except RuntimeError:
                    pass
        self._stroke_items = []
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.viewport().unsetCursor()

    def set_brush(self, size):
        self.brush = size
        if self._cursor_item:
            c = self._cursor_item.rect().center()
            self._cursor_item.setRect(c.x() - size / 2, c.y() - size / 2, size, size)

    def mask_array(self):
        m = QImage(self.img_size, QImage.Format.Format_Grayscale8)
        m.fill(0)
        p = QPainter(m)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        for path, size in self.strokes:
            p.setPen(QPen(QColor(255, 255, 255), size, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)
        p.end()
        w, h = m.width(), m.height()
        return np.frombuffer(m.constBits(), np.uint8).reshape(h, m.bytesPerLine())[:, :w].copy()

    def mousePressEvent(self, e):
        if self.erasing and e.button() == Qt.MouseButton.LeftButton:
            p = self.mapToScene(e.position().toPoint())
            self._cur = QPainterPath(p)
            self._cur.lineTo(p + QPointF(0.01, 0))
            pen = QPen(QColor(255, 50, 50, 140), self.brush, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            self._cur_item = self.sc.addPath(self._cur, pen)
            self._cur_item.setZValue(5)
            self._stroke_items.append(self._cur_item)
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        p = self.mapToScene(e.position().toPoint())
        x, y = int(p.x()), int(p.y())
        if self.item and 0 <= x < self.img_size.width() and 0 <= y < self.img_size.height():
            self.hoverPixel.emit(x, y)
        if self.erasing:
            if self._cursor_item:
                s = self.brush
                self._cursor_item.setRect(p.x() - s / 2, p.y() - s / 2, s, s)
                self._cursor_item.show()
            if self._cur is not None:
                self._cur.lineTo(p)
                self._cur_item.setPath(self._cur)
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self.erasing and self._cur is not None:
            self.strokes.append((self._cur, self.brush))
            self._cur = self._cur_item = None
            return
        super().mouseReleaseEvent(e)


# ------------------------------------------------------------------ 영역 캡처
class CaptureOverlay(QWidget):
    captured = Signal(QImage)
    cancelled = Signal()

    def __init__(self, pm):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.pm = pm
        self.a = self.b = None
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.showFullScreen()

    def sel(self):
        if self.a is None:
            return None
        return QRectF(self.a, self.b).normalized().toRect()

    def paintEvent(self, e):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self.pm)
        p.fillRect(self.rect(), QColor(0, 0, 0, 110))
        r = self.sel()
        if r and r.width() > 1:
            sx = self.pm.width() / self.width()
            p.drawPixmap(r, self.pm, QRectF(r.x() * sx, r.y() * sx, r.width() * sx, r.height() * sx))
            p.setPen(QPen(QColor("#4aa3ff"), 2))
            p.drawRect(r)
            p.setPen(QColor("white"))
            p.drawText(r.x() + 4, max(14, r.y() - 6), f"{int(r.width() * sx)} x {int(r.height() * sx)}")

    def mousePressEvent(self, e):
        self.a = self.b = e.position()
        self.update()

    def mouseMoveEvent(self, e):
        if self.a is not None:
            self.b = e.position()
            self.update()

    def mouseReleaseEvent(self, e):
        r = self.sel()
        self.close()
        if r and r.width() > 4 and r.height() > 4:
            sx = self.pm.width() / self.width()
            self.captured.emit(self.pm.copy(int(r.x() * sx), int(r.y() * sx), int(r.width() * sx),
                                            int(r.height() * sx)).toImage())
        else:
            self.cancelled.emit()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
            self.cancelled.emit()


# ------------------------------------------------------------------ 컨테이너(화살표 오버레이)
class Stage(QWidget):
    def __init__(self, viewer):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(viewer)
        self.overlays = []

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.relayout()

    def relayout(self):
        for w, place in self.overlays:
            place(w, self.width(), self.height())


NAV_STYLE = """
QToolButton{background:rgba(0,0,0,70);color:rgba(255,255,255,170);border:none;border-radius:26px;}
QToolButton:hover{background:rgba(0,0,0,170);color:white;}
"""


# ------------------------------------------------------------------ 메인 윈도우
class MainWindow(QMainWindow):
    def __init__(self, start_path=None):
        super().__init__()
        self.resize(1280, 800)
        self.setAcceptDrops(True)
        self.files, self.index = [], -1
        self.path = None
        self.image = None
        self.has_alpha = False
        self.modified = False
        self.history = []
        self.orig_image = None
        self.tasks = []
        self.progress = None

        self.viewer = Viewer()
        self.viewer.zoomChanged.connect(lambda z: self.lbl_zoom.setText(f"{round(z * 100)}%"))
        self.viewer.hoverPixel.connect(self.on_hover)
        self.viewer.contextRequested.connect(self.show_context_menu)
        self.stage = Stage(self.viewer)
        self.setCentralWidget(self.stage)

        self.build_actions()
        self.build_toolbar()
        self.build_status()
        self.build_overlays()
        self.build_thumbs()

        self.slide = QTimer(self)
        self.slide.setInterval(3000)
        self.slide.timeout.connect(lambda: self.navigate(1, silent=True))

        self.update_ui()
        if start_path:
            QTimer.singleShot(0, lambda: self.open_path(start_path))

    # ---------------------------------------------------------- UI 구성
    def act(self, text, slot, shortcut=None, icon=None):
        a = QAction(text, self)
        if icon:
            a.setIcon(icon)
        if shortcut:
            keys = shortcut if isinstance(shortcut, (list, tuple)) else [shortcut]
            a.setShortcuts([QKeySequence(k) for k in keys])
        a.triggered.connect(lambda checked=False: slot())
        self.addAction(a)
        return a

    def build_actions(self):
        global ICON_FONT
        ICON_FONT = _icon_font()
        g = glyph
        self.a_list = self.act("목록보기", self.toggle_thumbs, "Ctrl+L", g(0xE8FD, "☰"))
        self.a_list.setCheckable(True)
        self.a_full = self.act("전체화면", self.toggle_full, ["X", "F11"], g(0xE740, "⛶"))
        self.a_slide = self.act("연속보기", self.toggle_slide, ["S", "F5"], g(0xE768, "▶"))
        self.a_slide.setCheckable(True)
        self.a_left = self.act("-90° 회전", lambda: self.rotate(-90), "Ctrl+Left", g(0xE7A7, "↺"))
        self.a_right = self.act("90° 회전", lambda: self.rotate(90), ["Ctrl+Right", "R"], g(0xE7A6, "↻"))
        self.a_zout = self.act("축소", lambda: self.viewer.zoom_by(1 / 1.25), ["-", "Ctrl+-"], g(0xE71F, "−"))
        self.a_zin = self.act("확대", lambda: self.viewer.zoom_by(1.25), ["=", "+", "Ctrl+="], g(0xE8A3, "+"))
        self.a_orig = self.act("원본크기", lambda: self.viewer.set_zoom(1.0, True), "1", make_icon(draw_one))
        self.a_fit = self.act("창 맞춤", lambda: self.viewer.fit(True), ["0", "Ctrl+0"], make_icon(draw_fit))
        self.a_copy = self.act("복사", self.copy_image, "Ctrl+C", g(0xE8C8, "⧉"))
        self.a_del = self.act("삭제", self.delete_file, "Delete", g(0xE74D, "🗑"))
        self.a_ren = self.act("이름변경", self.rename_file, "F2", g(0xE8AC, "A"))
        self.a_cap = self.act("캡처하기", self.capture, "Ctrl+Shift+A", g(0xE7A8, "✂"))
        self.a_prev = self.act("이전", lambda: self.navigate(-1), ["Left", "PgUp", "Backspace"])
        self.a_next = self.act("다음", lambda: self.navigate(1), ["Right", "PgDown", "Space"])
        self.a_home = self.act("처음", lambda: self.goto(0), "Home")
        self.a_end = self.act("끝", lambda: self.goto(len(self.files) - 1), "End")
        self.a_open = self.act("파일 열기...", self.open_dialog, "Ctrl+O")
        self.a_save = self.act("다른 이름으로 저장...", self.save_as, ["Ctrl+S", "Ctrl+Shift+S"])
        self.a_undo = self.act("실행 취소", self.undo, "Ctrl+Z")
        self.a_revert = self.act("원본으로 되돌리기", self.revert)
        self.a_smooth = self.act("이미지를 부드럽게", self.toggle_smooth, "M")
        self.a_smooth.setCheckable(True)
        self.a_smooth.setChecked(True)
        self.a_arrange = self.act("이미지 배치", self.cycle_arrange, "D")
        self.a_print = self.act("인쇄하기", self.print_image, "Ctrl+P")
        self.a_props = self.act("파일속성", self.file_properties)
        self.a_esc = self.act("취소", self.on_escape, "Esc")
        self.a_enter = self.act("적용", self.apply_erase, ["Return", "Enter"])
        self.addAction(self.a_list)

    def build_toolbar(self):
        tb = QToolBar("main")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(30, 30))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        tb.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        tb.setStyleSheet("""
            QToolBar{background:white;border:none;border-bottom:1px solid #d9d9d9;spacing:2px;padding:4px 8px;}
            QToolButton{border:1px solid transparent;border-radius:3px;padding:5px 4px 3px 4px;
                        min-width:46px;font-family:'Malgun Gothic';font-size:9pt;color:#222;}
            QToolButton:hover{background:#eef3fb;border-color:#d6e2f5;}
            QToolButton:checked{background:#dfe9fa;border-color:#b9cdee;}
            QToolButton:disabled{color:#bbb;}
            QToolButton::menu-indicator{subcontrol-position:bottom center;subcontrol-origin:padding;bottom:-2px;}
            QToolBar::separator{background:#e3e3e3;width:1px;margin:6px 8px;}
        """)
        self.addToolBar(tb)
        self.toolbar = tb

        def add(a):
            tb.addAction(a)

        for a in (self.a_list, self.a_full, self.a_slide):
            add(a)
        tb.addSeparator()
        self.btn_ai = self.menu_button("AI 도구", make_icon(draw_ai), self.ai_menu())
        tb.addWidget(self.btn_ai)
        tb.addSeparator()
        for a in (self.a_left, self.a_right):
            add(a)
        tb.addSeparator()
        for a in (self.a_zout, self.a_zin, self.a_orig, self.a_fit):
            add(a)
        tb.addSeparator()
        for a in (self.a_copy, self.a_del, self.a_ren):
            add(a)
        tb.addSeparator()
        tb.addWidget(self.menu_button("편집하기", glyph(0xE70F, "✎"), self.edit_menu()))
        add(self.a_cap)
        tb.addSeparator()
        tb.addWidget(self.menu_button("더보기", glyph(0xE712, "…"), self.more_menu()))

    def menu_button(self, text, icon, menu):
        b = QToolButton()
        b.setText(text)
        b.setIcon(icon)
        b.setIconSize(QSize(30, 30))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        b.setMenu(menu)
        return b

    MENU_STYLE = ("QMenu{background:white;border:1px solid #9aa;font-family:'Malgun Gothic';font-size:9pt;padding:2px;}"
                  "QMenu::item{padding:4px 22px;}QMenu::item:selected{background:#cfe3fb;color:black;}"
                  "QMenu::item:disabled{color:#aaa;}")

    def ai_menu(self):
        m = QMenu(self)
        m.setStyleSheet(self.MENU_STYLE)
        self.ai_actions = []
        for text, fn in (("AI 화질 개선", self.ai_enhance), ("AI 배경 제거", self.ai_bg),
                         ("AI 텍스트 추출", self.ai_ocr), ("AI 얼굴 모자이크", self.ai_face),
                         ("AI 지우개", self.ai_erase)):
            a = m.addAction(text)
            a.triggered.connect(lambda checked=False, f=fn: f())
            self.ai_actions.append(a)
        return m

    def edit_menu(self):
        m = QMenu(self)
        m.setStyleSheet(self.MENU_STYLE)
        items = (("좌우 반전", lambda: self.edit_img(lambda i: i.mirrored(True, False))),
                 ("상하 반전", lambda: self.edit_img(lambda i: i.mirrored(False, True))),
                 ("흑백", lambda: self.edit_np(lambda b: np.dstack(
                     [np.repeat(np.dot(b[:, :, :3], [0.114, 0.587, 0.299]).astype(np.uint8)[:, :, None], 3, 2),
                      b[:, :, 3]]))),
                 ("밝게", lambda: self.edit_np(lambda b: self.adjust(b, 1.0, 20))),
                 ("어둡게", lambda: self.edit_np(lambda b: self.adjust(b, 1.0, -20))),
                 ("대비 높이기", lambda: self.edit_np(lambda b: self.adjust(b, 1.15, -10))),
                 ("선명하게", lambda: self.edit_np(self.sharpen)))
        for text, fn in items:
            m.addAction(text).triggered.connect(lambda checked=False, f=fn: f())
        return m

    def more_menu(self):
        m = QMenu(self)
        m.setStyleSheet(self.MENU_STYLE)
        for text, fn in (("파일 열기...", self.open_dialog), ("저장 / 다른 이름으로 저장...", self.save_as),
                         ("실행 취소  (Ctrl+Z)", self.undo), ("원본으로 되돌리기", self.revert),
                         ("파일 위치 열기", self.reveal), ("파일 정보", self.show_info)):
            m.addAction(text).triggered.connect(lambda checked=False, f=fn: f())
        return m

    def build_status(self):
        sb = self.statusBar()
        sb.setStyleSheet("QStatusBar{background:#f3f3f3;border-top:1px solid #d0d0d0;}"
                         "QLabel{font-family:'Malgun Gothic';font-size:9pt;color:#222;padding:0 10px;}")
        sb.setSizeGripEnabled(False)
        self.lbl_idx, self.lbl_dim, self.lbl_size, self.lbl_zoom = (QLabel("0 / 0"), QLabel(""), QLabel(""), QLabel(""))
        self.lbl_pos, self.lbl_rgb = QLabel(""), QLabel("")
        for w in (self.lbl_idx, self.lbl_dim, self.lbl_size, self.lbl_zoom):
            sb.addWidget(w)
        sb.addPermanentWidget(self.lbl_pos)
        sb.addPermanentWidget(self.lbl_rgb)

    def build_overlays(self):
        def nav(code, fb):
            b = QToolButton(self.stage)
            b.setFixedSize(52, 52)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(NAV_STYLE)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            f = QFont(ICON_FONT or "Malgun Gothic")
            f.setPixelSize(22)
            b.setFont(f)
            b.setText(chr(code) if ICON_FONT else fb)
            return b

        self.btn_prev = nav(0xE76B, "‹")
        self.btn_next = nav(0xE76C, "›")
        self.btn_prev.clicked.connect(lambda: self.navigate(-1))
        self.btn_next.clicked.connect(lambda: self.navigate(1))
        self.stage.overlays.append((self.btn_prev, lambda w, W, H: w.move(14, (H - 52) // 2)))
        self.stage.overlays.append((self.btn_next, lambda w, W, H: w.move(W - 66, (H - 52) // 2)))

        # 지우개 패널
        p = QFrame(self.stage)
        p.setStyleSheet("QFrame{background:rgba(25,25,25,225);border-radius:8px;}"
                        "QLabel{color:white;font-family:'Malgun Gothic';font-size:9pt;background:transparent;}"
                        "QPushButton{font-family:'Malgun Gothic';padding:5px 14px;border-radius:4px;border:none;}")
        lay = QHBoxLayout(p)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.addWidget(QLabel("AI 지우개 - 지울 부분을 칠하세요   브러시 크기"))
        self.sld = QSlider(Qt.Orientation.Horizontal)
        self.sld.setRange(5, 300)
        self.sld.setFixedWidth(140)
        self.sld.valueChanged.connect(self.viewer.set_brush)
        lay.addWidget(self.sld)
        ok = QPushButton("지우기 (Enter)")
        ok.setStyleSheet("background:#3b82f6;color:white;")
        ok.clicked.connect(self.apply_erase)
        no = QPushButton("취소 (Esc)")
        no.setStyleSheet("background:#555;color:white;")
        no.clicked.connect(self.cancel_erase)
        lay.addWidget(ok)
        lay.addWidget(no)
        p.adjustSize()
        p.hide()
        self.erase_panel = p
        self.stage.overlays.append((p, lambda w, W, H: w.move((W - w.width()) // 2, 14)))

    def build_thumbs(self):
        self.thumbs = QListWidget()
        self.thumbs.setViewMode(QListWidget.ViewMode.IconMode)
        self.thumbs.setFlow(QListWidget.Flow.LeftToRight)
        self.thumbs.setWrapping(False)
        self.thumbs.setMovement(QListWidget.Movement.Static)
        self.thumbs.setIconSize(QSize(120, 80))
        self.thumbs.setGridSize(QSize(132, 108))
        self.thumbs.setFixedHeight(128)
        self.thumbs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.thumbs.setStyleSheet("QListWidget{background:#202020;border:none;color:#ddd;font-size:8pt;}"
                                  "QListWidget::item:selected{background:#3b6fb8;color:white;}")
        self.thumbs.itemClicked.connect(lambda it: self.goto(self.thumbs.row(it)))
        self.dock = QDockWidget(self)
        self.dock.setTitleBarWidget(QWidget())
        self.dock.setWidget(self.thumbs)
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock)
        self.dock.hide()

    # ---------------------------------------------------------- 파일 / 탐색
    def open_dialog(self):
        flt = "이미지 (" + " ".join(f"*.{e}" for e in sorted(EXTS)) + ");;모든 파일 (*.*)"
        start = os.path.dirname(self.path) if self.path else ""
        p, _ = QFileDialog.getOpenFileName(self, "파일 열기", start, flt)
        if p:
            self.open_path(p)

    def read_image(self, path):
        r = QImageReader(path)
        r.setAutoTransform(True)
        img = r.read()
        if img.isNull():
            return None, False
        alpha = img.hasAlphaChannel()
        img = img.convertToFormat(QImage.Format.Format_ARGB32 if alpha else QImage.Format.Format_RGB32)
        return img, alpha

    def open_path(self, path):
        path = os.path.abspath(path)
        if os.path.isdir(path):
            folder, target = path, None
        else:
            folder, target = os.path.dirname(path), path
        if not self.confirm_discard():
            return
        files = sorted((os.path.join(folder, f) for f in os.listdir(folder)
                        if f.rsplit(".", 1)[-1].lower() in EXTS and "." in f),
                       key=lambda p: natural_key(os.path.basename(p)))
        if not files:
            QMessageBox.information(self, APP_NAME, "폴더에 열 수 있는 이미지가 없습니다.")
            return
        self.files = files
        self.fill_thumbs()
        idx = 0
        if target:
            try:
                idx = [os.path.normcase(f) for f in files].index(os.path.normcase(target))
            except ValueError:
                idx = 0
        self.show_index(idx)

    def show_index(self, i):
        img, alpha = self.read_image(self.files[i])
        if img is None:
            QMessageBox.warning(self, APP_NAME, f"이미지를 열 수 없습니다:\n{self.files[i]}")
            return False
        self.index = i
        self.path = self.files[i]
        self.set_loaded(img, alpha)
        self.thumbs.setCurrentRow(i)
        return True

    def set_loaded(self, img, alpha):
        self.image, self.has_alpha = img, alpha
        self.orig_image = img
        self.history = []
        self.modified = False
        self.viewer.set_image(img, checker=alpha)
        self.update_ui()

    def confirm_discard(self):
        if not self.modified:
            return True
        r = QMessageBox.question(self, APP_NAME, "편집한 내용이 저장되지 않았습니다. 저장할까요?",
                                 QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                 | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Save:
            return self.save_as()
        return r == QMessageBox.StandardButton.Discard

    def navigate(self, d, silent=False):
        if len(self.files) < 2 or self.viewer.erasing:
            return
        if not self.confirm_discard():
            self.a_slide.setChecked(False)
            self.slide.stop()
            return
        self.modified = False
        self.show_index((self.index + d) % len(self.files))

    def goto(self, i):
        if 0 <= i < len(self.files) and i != self.index and not self.viewer.erasing:
            if self.confirm_discard():
                self.modified = False
                self.show_index(i)

    def fill_thumbs(self):
        self.thumbs.clear()
        self._thumb_gen = time.time()
        gen = self._thumb_gen
        blank = QPixmap(120, 80)
        blank.fill(QColor("#333"))
        for f in self.files:
            it = QListWidgetItem(QIcon(blank), os.path.basename(f))
            it.setSizeHint(QSize(132, 108))
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.thumbs.addItem(it)

        def step(start):
            if gen != self._thumb_gen:
                return
            for i in range(start, min(start + 6, len(self.files))):
                r = QImageReader(self.files[i])
                r.setAutoTransform(True)
                sz = r.size()
                if sz.isValid():
                    r.setScaledSize(sz.scaled(120, 80, Qt.AspectRatioMode.KeepAspectRatio))
                im = r.read()
                if not im.isNull():
                    self.thumbs.item(i).setIcon(QIcon(QPixmap.fromImage(im)))
            if start + 6 < len(self.files):
                QTimer.singleShot(5, lambda: step(start + 6))

        QTimer.singleShot(0, lambda: step(0))

    def toggle_thumbs(self):
        self.dock.setVisible(self.a_list.isChecked())
        if self.a_list.isChecked():
            self.thumbs.scrollToItem(self.thumbs.currentItem())

    def toggle_full(self):
        if self.isFullScreen():
            self.showNormal()
            self.toolbar.show()
            self.statusBar().show()
        else:
            self.showFullScreen()
            self.toolbar.hide()
            self.statusBar().hide()

    def toggle_slide(self):
        if self.a_slide.isChecked() and len(self.files) > 1:
            self.slide.start()
        else:
            self.a_slide.setChecked(False)
            self.slide.stop()

    def on_escape(self):
        if self.viewer.erasing:
            self.cancel_erase()
        elif self.isFullScreen():
            self.toggle_full()

    # ---------------------------------------------------------- 상태 표시
    def update_ui(self):
        has = self.image is not None
        n = len(self.files)
        multi = n > 1 and has
        self.btn_prev.setVisible(multi and not self.viewer.erasing)
        self.btn_next.setVisible(multi and not self.viewer.erasing)
        self.a_slide.setEnabled(multi)
        for a in (self.a_left, self.a_right, self.a_zin, self.a_zout, self.a_orig, self.a_fit,
                  self.a_copy, self.a_cap):
            a.setEnabled(has if a is not self.a_cap else True)
        for a in (self.a_del, self.a_ren):
            a.setEnabled(has and bool(self.path) and os.path.exists(self.path or ""))
        self.btn_ai.setEnabled(has)
        self.stage.relayout()
        if not has:
            self.setWindowTitle(APP_NAME)
            return
        name = os.path.basename(self.path) if self.path else "이름 없음"
        self.setWindowTitle(f"{APP_NAME} - {name}{' *' if self.modified else ''}")
        self.lbl_idx.setText(f"{self.index + 1} / {n}" if self.path and n else "1 / 1")
        self.lbl_dim.setText(f"{self.image.width()} x {self.image.height()} x {32 if self.has_alpha else 24}")
        if self.path and os.path.exists(self.path) and not self.modified:
            self.lbl_size.setText(f"{os.path.getsize(self.path) / 1048576:.2f}MB")
        else:
            self.lbl_size.setText("편집됨" if self.modified else "")
        self.lbl_zoom.setText(f"{round(self.viewer.zoom * 100)}%")

    def on_hover(self, x, y):
        self.lbl_pos.setText(f"X : {x}, Y : {y}")
        if self.image:
            c = self.image.pixelColor(x, y)
            self.lbl_rgb.setText(f"{c.red():03d}, {c.green():03d}, {c.blue():03d}")

    # ---------------------------------------------------------- 편집 공통
    def apply_edit(self, img, alpha=None):
        self.history.append((self.image, self.has_alpha))
        self.history = self.history[-8:]
        if alpha is not None:
            self.has_alpha = alpha
        if not self.has_alpha:
            img = img.convertToFormat(QImage.Format.Format_RGB32)
        self.image = img
        self.modified = True
        self.viewer.set_image(img, keep_view=True, checker=self.has_alpha)
        self.update_ui()

    def undo(self):
        if self.viewer.erasing:
            return
        if self.history:
            self.image, self.has_alpha = self.history.pop()
            self.modified = bool(self.history)
            self.viewer.set_image(self.image, keep_view=True, checker=self.has_alpha)
            self.update_ui()

    def revert(self):
        if self.image is not None and self.orig_image is not None and self.modified:
            self.history = []
            self.image = self.orig_image
            self.has_alpha = self.orig_image.hasAlphaChannel() and self.orig_image.format() == QImage.Format.Format_ARGB32
            self.modified = False
            self.viewer.set_image(self.image, checker=self.has_alpha)
            self.update_ui()

    def rotate(self, deg):
        if self.image is not None and not self.viewer.erasing:
            self.apply_edit(self.image.transformed(QTransform().rotate(deg), Qt.TransformationMode.SmoothTransformation))
            self.viewer.fit(False)

    def edit_img(self, fn):
        if self.image is not None and not self.viewer.erasing:
            self.apply_edit(fn(self.image))

    def edit_np(self, fn):
        if self.image is not None and not self.viewer.erasing:
            self.apply_edit(bgra_to_qimage(fn(qimage_to_bgra(self.image))))

    @staticmethod
    def adjust(b, alpha, beta):
        out = b.copy()
        out[:, :, :3] = np.clip(b[:, :, :3].astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)
        return out

    @staticmethod
    def sharpen(b):
        import cv2
        out = b.copy()
        blur = cv2.GaussianBlur(b[:, :, :3], (0, 0), 1.5)
        out[:, :, :3] = cv2.addWeighted(b[:, :, :3], 1.8, blur, -0.8, 0)
        return out

    # ---------------------------------------------------------- 파일 작업
    def copy_image(self):
        if self.image is not None:
            QApplication.clipboard().setImage(self.image)
            self.statusBar().showMessage("클립보드에 복사했습니다.", 2000)

    def delete_file(self):
        if not self.path or not os.path.exists(self.path):
            return
        r = QMessageBox.question(self, "삭제", f"'{os.path.basename(self.path)}' 파일을 휴지통으로 보낼까요?")
        if r != QMessageBox.StandardButton.Yes:
            return
        if not QFile.moveToTrash(self.path):
            QMessageBox.warning(self, "삭제", "삭제하지 못했습니다.")
            return
        self.modified = False
        del self.files[self.index]
        self.fill_thumbs()
        if not self.files:
            self.index, self.path, self.image = -1, None, None
            self.viewer.clear()
            self.update_ui()
            return
        self.show_index(min(self.index, len(self.files) - 1))

    def rename_file(self):
        if not self.path:
            return
        stem, ext = os.path.splitext(os.path.basename(self.path))
        new, ok = QInputDialog.getText(self, "이름변경", "새 파일 이름:", text=stem)
        if not ok or not new.strip() or new == stem:
            return
        dst = os.path.join(os.path.dirname(self.path), new.strip() + ext)
        if os.path.exists(dst):
            QMessageBox.warning(self, "이름변경", "같은 이름의 파일이 이미 있습니다.")
            return
        try:
            os.rename(self.path, dst)
        except OSError as e:
            QMessageBox.warning(self, "이름변경", str(e))
            return
        self.files[self.index] = self.path = dst
        self.fill_thumbs()
        self.thumbs.setCurrentRow(self.index)
        self.update_ui()

    def save_as(self):
        if self.image is None:
            return False
        base = os.path.splitext(os.path.basename(self.path))[0] if self.path else "capture"
        d = os.path.dirname(self.path) if self.path else os.path.expanduser("~/Pictures")
        suffix = "_edit" if self.modified else ""
        default = os.path.join(d, base + suffix + (".png" if self.has_alpha or not self.path else ".jpg"))
        p, _ = QFileDialog.getSaveFileName(self, "저장", default,
                                           "PNG (*.png);;JPEG (*.jpg *.jpeg);;WebP (*.webp);;BMP (*.bmp)")
        if not p:
            return False
        img = self.image
        if p.lower().endswith((".jpg", ".jpeg", ".bmp")) and img.hasAlphaChannel():
            bg = QImage(img.size(), QImage.Format.Format_RGB32)
            bg.fill(QColor("white"))
            qp = QPainter(bg)
            qp.drawImage(0, 0, img)
            qp.end()
            img = bg
        if not img.save(p, quality=95):
            QMessageBox.warning(self, "저장", "저장하지 못했습니다.")
            return False
        self.modified = False
        self.files_reload_to(p)
        return True

    def files_reload_to(self, p):
        folder = os.path.dirname(p)
        self.files = sorted((os.path.join(folder, f) for f in os.listdir(folder)
                             if "." in f and f.rsplit(".", 1)[-1].lower() in EXTS),
                            key=lambda x: natural_key(os.path.basename(x)))
        self.fill_thumbs()
        keep = self.image, self.has_alpha
        i = [os.path.normcase(f) for f in self.files].index(os.path.normcase(os.path.abspath(p)))
        self.index, self.path = i, self.files[i]
        self.image, self.has_alpha = keep
        self.history = []
        self.orig_image = self.image
        self.thumbs.setCurrentRow(i)
        self.update_ui()

    def reveal(self):
        if self.path:
            os.startfile(os.path.dirname(self.path))

    def show_info(self):
        if self.image is None:
            return
        lines = [f"이름: {os.path.basename(self.path) if self.path else '(저장 안 됨)'}",
                 f"크기: {self.image.width()} x {self.image.height()}"]
        if self.path and os.path.exists(self.path):
            fi = QFileInfo(self.path)
            lines += [f"경로: {self.path}", f"용량: {fi.size() / 1048576:.2f} MB",
                      f"수정한 날짜: {fi.lastModified().toString('yyyy-MM-dd HH:mm:ss')}"]
        QMessageBox.information(self, "파일 정보", "\n".join(lines))

    # ---------------------------------------------------------- 오른쪽 클릭 메뉴
    def show_context_menu(self, pos):
        if self.image is None or self.viewer.erasing:
            return
        m = QMenu(self)
        m.setStyleSheet(self.MENU_STYLE)
        # 단축키 표시는 메뉴 항목 텍스트에 직접 적는다 (창 전체 단축키와 중복 방지)
        def item(text, key, fn, checked=None):
            a = m.addAction(f"{text}	{key}" if key else text)
            if checked is not None:
                a.setCheckable(True)
                a.setChecked(checked)
            a.triggered.connect(lambda checked=False: fn())
            return a
        item("전체화면", "X", self.toggle_full)
        a = item("연속보기", "S", self.a_slide.trigger)
        a.setEnabled(len(self.files) > 1)
        a.setCheckable(True)
        a.setChecked(self.a_slide.isChecked())
        m.addSeparator()
        item("이미지를 부드럽게", "M", self.toggle_smooth, self.viewer.smooth)
        sub = m.addMenu("이미지 배치	D")
        sub.setStyleSheet(self.MENU_STYLE)
        cur = {"shrink": 0, "fit": 1, None: 2}.get(self.viewer.fit_mode, 2)
        for i, (text, fn) in enumerate((("창에 맞추기 (큰 사진만 축소)", lambda: self.viewer.fit(False)),
                                        ("창에 맞추기 (확대 포함)", lambda: self.viewer.fit(True)),
                                        ("원본 크기", lambda: self.viewer.set_zoom(1.0, True)))):
            x = sub.addAction(text)
            x.setCheckable(True)
            x.setChecked(i == cur)
            x.triggered.connect(lambda checked=False, f=fn: f())
        m.addSeparator()
        item("인쇄하기", "Ctrl+P", self.print_image)
        item("파일속성", "", self.file_properties)
        m.exec(pos)

    def toggle_smooth(self):
        self.viewer.smooth = not self.viewer.smooth
        self.a_smooth.setChecked(self.viewer.smooth)
        self.viewer.apply_smooth()

    def cycle_arrange(self):
        order = [lambda: self.viewer.fit(False), lambda: self.viewer.fit(True),
                 lambda: self.viewer.set_zoom(1.0, True)]
        cur = {"shrink": 0, "fit": 1, None: 2}.get(self.viewer.fit_mode, 2)
        order[(cur + 1) % 3]()

    def print_image(self):
        if self.image is None:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dlg = QPrintDialog(printer, self)
        dlg.setWindowTitle("인쇄하기")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        p = QPainter(printer)
        rect = printer.pageRect(QPrinter.Unit.DevicePixel).toRect()
        img = self.image
        size = img.size().scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = rect.x() + (rect.width() - size.width()) // 2
        y = rect.y() + (rect.height() - size.height()) // 2
        p.drawImage(QRectF(x, y, size.width(), size.height()), img)
        p.end()

    def file_properties(self):
        if not self.path or not os.path.exists(self.path):
            self.show_info()
            return

        class SEI(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND),
                        ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR),
                        ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR),
                        ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                        ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR),
                        ("hkeyClass", wintypes.HKEY), ("dwHotKey", wintypes.DWORD),
                        ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]
        info = SEI()
        info.cbSize = ctypes.sizeof(SEI)
        info.fMask = 0x0000000C  # SEE_MASK_INVOKEIDLIST
        info.lpVerb = "properties"
        info.lpFile = os.path.normpath(self.path)
        info.nShow = 5
        if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
            self.show_info()

    # ---------------------------------------------------------- 캡처
    def capture(self):
        if self.viewer.erasing:
            return
        self.hide()
        QTimer.singleShot(350, self._grab)

    def _grab(self):
        pm = QApplication.primaryScreen().grabWindow(0)
        self.overlay = CaptureOverlay(pm)
        self.overlay.captured.connect(self._captured)
        self.overlay.cancelled.connect(self.show_restored)

    def _captured(self, img):
        self.show_restored()
        if not self.confirm_discard():
            return
        self.path, self.files, self.index = None, [], -1
        self.set_loaded(img.convertToFormat(QImage.Format.Format_RGB32), False)
        self.modified = True
        self.update_ui()

    def show_restored(self):
        self.show()
        self.activateWindow()

    # ---------------------------------------------------------- AI
    def run_task(self, label, fn, on_done, determinate=False):
        if self.image is None:
            return
        dlg = QProgressDialog(label, None, 0, 100 if determinate else 0, self)
        dlg.setWindowTitle(APP_NAME)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setCancelButton(None)
        dlg.setMinimumWidth(360)
        dlg.show()
        self.progress = dlg
        task = Task(fn)
        self.tasks.append(task)

        def finish():
            dlg.close()
            self.tasks.remove(task)

        def ok(res):
            finish()
            on_done(res)

        def bad(msg):
            finish()
            QMessageBox.warning(self, APP_NAME, f"작업에 실패했습니다.\n\n{msg}")

        task.signals.prog.connect(lambda v: dlg.setValue(v) if determinate else None)
        task.signals.done.connect(ok)
        task.signals.fail.connect(bad)
        QThreadPool.globalInstance().start(task)

    def ai_enhance(self):
        arr = qimage_to_bgra(self.image)
        self.run_task("AI 화질 개선 중입니다...", lambda p: ai_tools.enhance(arr, p),
                      lambda r: (self.apply_edit(bgra_to_qimage(r)), self.viewer.fit(False)), True)

    def ai_bg(self):
        arr = qimage_to_bgra(self.image)
        self.run_task("AI 배경 제거 중입니다...\n(처음 한 번은 AI 모델을 내려받느라 오래 걸립니다)",
                      lambda p: ai_tools.remove_background(arr, p),
                      lambda r: self.apply_edit(bgra_to_qimage(r), alpha=True))

    def ai_face(self):
        arr = qimage_to_bgra(self.image)

        def done(res):
            out, n = res
            if n == 0:
                QMessageBox.information(self, APP_NAME, "얼굴을 찾지 못했습니다.")
            else:
                self.apply_edit(bgra_to_qimage(out))
                self.statusBar().showMessage(f"얼굴 {n}개에 모자이크를 적용했습니다.", 4000)

        self.run_task("AI 얼굴을 찾는 중입니다...", lambda p: ai_tools.mosaic_faces(arr, p), done)

    def ai_ocr(self):
        arr = qimage_to_bgra(self.image)
        self.run_task("AI 텍스트를 추출하는 중입니다...", lambda p: ai_tools.extract_text(arr, p), self.show_text)

    def show_text(self, text):
        dlg = QDialog(self)
        dlg.setWindowTitle("AI 텍스트 추출")
        dlg.resize(560, 420)
        lay = QVBoxLayout(dlg)
        box = QPlainTextEdit(text or "")
        box.setPlaceholderText("추출된 텍스트가 없습니다.")
        box.setFont(QFont("Malgun Gothic", 10))
        lay.addWidget(box)
        row = QHBoxLayout()
        row.addStretch()
        cp = QPushButton("전체 복사")
        cp.clicked.connect(lambda: (QApplication.clipboard().setText(box.toPlainText()),
                                    self.statusBar().showMessage("텍스트를 복사했습니다.", 2000)))
        cl = QPushButton("닫기")
        cl.clicked.connect(dlg.accept)
        row.addWidget(cp)
        row.addWidget(cl)
        lay.addLayout(row)
        dlg.exec()

    def ai_erase(self):
        if self.viewer.erasing:
            return
        size = max(12, self.image.width() // 60)
        self.sld.blockSignals(True)
        self.sld.setValue(min(300, size))
        self.sld.blockSignals(False)
        self.slide.stop()
        self.a_slide.setChecked(False)
        self.viewer.begin_erase(self.sld.value())
        self.erase_panel.show()
        self.erase_panel.raise_()
        self.update_ui()

    def cancel_erase(self):
        self.viewer.end_erase()
        self.erase_panel.hide()
        self.update_ui()

    def apply_erase(self):
        if not self.viewer.erasing:
            return
        if not self.viewer.strokes:
            self.cancel_erase()
            return
        mask = self.viewer.mask_array()
        arr = qimage_to_bgra(self.image)
        self.viewer.end_erase()
        self.erase_panel.hide()
        self.run_task("AI 지우개 적용 중입니다...", lambda p: ai_tools.inpaint(arr, mask, p),
                      lambda r: self.apply_edit(bgra_to_qimage(r)))

    # ---------------------------------------------------------- 이벤트
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            if u.isLocalFile():
                self.open_path(u.toLocalFile())
                break

    def closeEvent(self, e):
        if self.confirm_discard():
            e.accept()
        else:
            e.ignore()


def selftest(out_path):
    """빌드된 exe에서 AI 기능이 모두 로드되는지 확인 (--selftest 결과파일)"""
    res = []
    arr = np.full((300, 300, 4), 200, np.uint8)
    for name, fn in (("enhance", lambda: ai_tools.enhance(arr)), ("bg", lambda: ai_tools.remove_background(arr)),
                     ("ocr", lambda: ai_tools.extract_text(arr)), ("face", lambda: ai_tools.mosaic_faces(arr)),
                     ("inpaint", lambda: ai_tools.inpaint(arr, np.zeros((300, 300), np.uint8)))):
        try:
            fn()
            res.append(f"{name}: OK")
        except Exception as e:  # noqa
            res.append(f"{name}: FAIL {e!r}")
    open(out_path, "w", encoding="utf-8").write("\n".join(res))


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--selftest":
        return selftest(sys.argv[2])
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(QFont("Malgun Gothic", 9))
    w = MainWindow(sys.argv[1] if len(sys.argv) > 1 else None)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
