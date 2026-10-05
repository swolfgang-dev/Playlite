from .theme import set_style
"""Hidden scrollbars with edge fades indicating additional content."""
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import QScrollArea, QWidget, QGraphicsEffect


class ContentFade(QGraphicsEffect):
    """Fade only scrolling content, leaving the panel/backdrop untouched."""
    def __init__(self, fades):
        super().__init__(fades)
        self.fades = fades

    def draw(self, painter):
        fades = self.fades
        bar = fades.area.horizontalScrollBar() if fades.horizontal else fades.area.verticalScrollBar()
        if bar.maximum() <= bar.minimum():
            self.drawSource(painter)
            return
        pixmap, offset = self.sourcePixmap(Qt.CoordinateSystem.LogicalCoordinates,
                                           QGraphicsEffect.PixmapPadMode.NoPad)
        if pixmap.isNull():
            return
        size = pixmap.deviceIndependentSize()
        width, height = size.width(), size.height()
        extent = width if fades.horizontal else height
        edge = min(20, extent / 3)
        if edge <= 0:
            self.drawSource(painter)
            return
        gradient = QLinearGradient(0, 0, width if fades.horizontal else 0,
                                    0 if fades.horizontal else height)
        clear = QColor(0, 0, 0, 0)
        solid = QColor(0, 0, 0, 255)
        gradient.setColorAt(0, clear if bar.value() > bar.minimum() else solid)
        gradient.setColorAt(edge / extent, solid)
        gradient.setColorAt(1 - edge / extent, solid)
        gradient.setColorAt(1, clear if bar.value() < bar.maximum() else solid)
        masked = pixmap.copy()
        mask_painter = QPainter(masked)
        mask_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        from PyQt6.QtCore import QRectF
        mask_painter.fillRect(QRectF(0, 0, width, height), gradient)
        mask_painter.end()
        painter.drawPixmap(offset, masked)


class ScrollFades(QWidget):
    def __init__(self, area, horizontal=False):
        super().__init__(area)
        self.area = area
        self.horizontal = horizontal
        set_style(self, 'background: transparent;')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.effect = ContentFade(self)
        area.viewport().setGraphicsEffect(self.effect)
        area.viewport().installEventFilter(self)
        bar = area.horizontalScrollBar() if horizontal else area.verticalScrollBar()
        bar.valueChanged.connect(self.refresh)
        bar.rangeChanged.connect(self.refresh)
        self.setGeometry(area.viewport().geometry())
        self.show()

    def refresh(self, *args):
        self.setGeometry(self.area.viewport().geometry())
        self.effect.update()

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show):
            self.refresh()
        return False

    def paintEvent(self, event):
        pass

    def hideEvent(self, event):
        self.effect.setEnabled(False)
        super().hideEvent(event)

    def showEvent(self, event):
        self.effect.setEnabled(True)
        super().showEvent(event)


class HorizontalValuesScroll(QScrollArea):
    def wheelEvent(self, event):
        bar = self.horizontalScrollBar()
        if bar.maximum() <= bar.minimum():
            event.ignore()
            return
        pixels = event.pixelDelta()
        angles = event.angleDelta()
        delta = pixels.x() or pixels.y()
        if not delta:
            delta = (angles.x() or angles.y()) / 120 * 60
        bar.setValue(bar.value() - round(delta))
        event.accept()
