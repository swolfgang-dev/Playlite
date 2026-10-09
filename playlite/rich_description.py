from .theme import set_style
"""Rich descriptions with optional collapsible, scrolling game-view panels."""
import math
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QVariantAnimation, QEasingCurve, QPoint
from PyQt6.QtWidgets import QTextBrowser, QSizePolicy, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QScrollArea
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QTextFormat, QTextBlockFormat
from .description_html import without_images
from .scroll_fades import ScrollFades


def set_description_html(viewer, content):
    """Use the UI text size while retaining emphasis, links and paragraph layout."""
    viewer.ensurePolished()
    font = viewer.font()
    viewer.document().setDefaultFont(font)
    viewer.setHtml(content)
    cursor = QTextCursor(viewer.document())
    cursor.select(QTextCursor.SelectionType.Document)
    formatting = QTextCharFormat()
    formatting.setProperty(QTextFormat.Property.FontSizeAdjustment, 0)
    if font.pixelSize() > 0:
        formatting.setProperty(QTextFormat.Property.FontPixelSize, font.pixelSize())
    else:
        formatting.setFontPointSize(font.pointSizeF())
    cursor.mergeCharFormat(formatting)
    # Imported paragraph margins and empty lines can otherwise leave large gaps.
    blank_format = QTextCharFormat()
    blank_format.setProperty(QTextFormat.Property.FontPixelSize, 2)
    block = viewer.document().begin()
    while block.isValid():
        cursor = QTextCursor(block)
        spacing = block.blockFormat()
        spacing.setTopMargin(0)
        spacing.setBottomMargin(8 if block.text().strip() and block.next().isValid() else 0)
        if not block.text().strip():
            spacing.setLineHeight(2, QTextBlockFormat.LineHeightTypes.FixedHeight.value)
        cursor.setBlockFormat(spacing)
        # HTML <br> creates a line separator inside a paragraph, rather than a block.
        text = block.text()
        for index, character in enumerate(text):
            if character == '\u2028' and not text[:index].rsplit('\u2028', 1)[-1].strip():
                cursor.setPosition(block.position() + index)
                cursor.setPosition(block.position() + index + 1, QTextCursor.MoveMode.KeepAnchor)
                cursor.mergeCharFormat(blank_format)
        block = block.next()


class FullDescription(QTextBrowser):
    contentResized = pyqtSignal()
    clicked = pyqtSignal()

    def __init__(self, content, parent=None):
        super().__init__(parent)
        self.animating = False
        self.expanded = True
        self.scrollable = False
        self.expanded_height = 480
        self.collapsed_height = 180
        self.content_height = 0
        self.setObjectName('description')
        self.setFrameShape(QFrame.Shape.NoFrame)
        set_style(self, 'QTextBrowser { border: 0; background: transparent; }')
        self.setOpenExternalLinks(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.document().setDocumentMargin(0)
        self.layout_timer = QTimer(self)
        self.layout_timer.setSingleShot(True)
        self.layout_timer.timeout.connect(self.fit_content)
        self.document().documentLayout().documentSizeChanged.connect(lambda _: self.layout_timer.start(0))
        set_description_html(self, without_images(content))
        self.layout_timer.start(0)

    def loadResource(self, kind, url):
        return None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.layout_timer.start(0)

    def fit_content(self):
        self.document().setTextWidth(max(1, self.viewport().width()))
        natural_height = math.ceil(self.document().size().height()) + self.frameWidth() * 2 + 4
        changed = self.content_height != natural_height
        self.content_height = natural_height
        limit = self.expanded_height if self.expanded else self.collapsed_height
        height = min(natural_height, limit) if self.scrollable else natural_height
        if not self.animating and self.height() != height:
            self.setFixedHeight(height)
            changed = True
        if changed:
            self.contentResized.emit()

    def sizeHint(self):
        return QSize(super().sizeHint().width(), self.height())

    def mousePressEvent(self, event):
        if self.scrollable and not self.expanded and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        bar = self.verticalScrollBar()
        delta = event.pixelDelta().y() or event.angleDelta().y() / 120 * 60
        if (not self.scrollable or bar.maximum() <= bar.minimum() or not delta
                or (delta > 0 and bar.value() <= bar.minimum())
                or (delta < 0 and bar.value() >= bar.maximum())):
            event.ignore()
            return
        bar.setValue(bar.value() - round(delta))
        event.accept()


class CollapsibleDescription(QWidget):
    expanded = pyqtSignal()
    def __init__(self, content, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.description = FullDescription(content)
        self.description.expanded = False
        self.description.scrollable = True
        self.description.fades = ScrollFades(self.description)
        layout.addWidget(self.description)
        row = QHBoxLayout()
        row.addStretch()
        self.toggle = QPushButton('Hide')
        set_style(self.toggle, 'QPushButton { background: transparent; border: 0; color: #999a9d; } QPushButton:hover { color: #b3b4b7; } QPushButton:pressed { color: #85868a; }')
        self.toggle.clicked.connect(self.toggle_expanded)
        self.description.clicked.connect(self.open_panel)
        self.height_animation = QVariantAnimation(self)
        self.height_animation.setDuration(350)
        self.height_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.height_animation.valueChanged.connect(self.animate_frame)
        self.height_animation.finished.connect(self.finish_animation)
        self.page_scroll = None
        row.addWidget(self.toggle)
        row.addStretch()
        layout.addLayout(row)
        self.description.contentResized.connect(self.update_button)
        self.description.fit_content()
        self.description.verticalScrollBar().setValue(0)
        self.update_button()

    def update_button(self):
        self.toggle.setVisible((self.description.expanded or self.description.animating) and self.description.content_height > self.description.collapsed_height)
        self.description.viewport().setCursor(Qt.CursorShape.ArrowCursor if self.description.expanded else Qt.CursorShape.PointingHandCursor)

    def open_panel(self):
        if not self.description.expanded and self.description.content_height > self.description.collapsed_height:
            self.toggle_expanded()

    def toggle_expanded(self):
        self.height_animation.stop()
        self.description.expanded = not self.description.expanded
        self.description.animating = True
        self.description.fit_content()
        if self.description.expanded:
            self.description.verticalScrollBar().setValue(0)
        self.update_button()
        limit = self.description.expanded_height if self.description.expanded else self.description.collapsed_height
        self.button_start_height = self.toggle.height()
        self.start_height = self.description.height()
        self.end_height = min(self.description.content_height, limit)
        self.prepare_scroll()
        self.height_animation.setStartValue(self.start_height)
        self.height_animation.setEndValue(self.end_height)
        self.height_animation.start()

    def finish_animation(self):
        self.description.animating = False
        self.description.fit_content()
        if not self.description.expanded:
            self.description.verticalScrollBar().setValue(0)
        self.update_button()
        if not self.description.expanded:
            self.toggle.setFixedHeight(self.button_start_height)
        if self.description.expanded:
            self.expanded.emit()

    def prepare_scroll(self):
        self.page_scroll = None
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QScrollArea):
            parent = parent.parentWidget()
        if parent is None:
            return
        self.page_scroll = parent
        card = self.parentWidget() if self.parentWidget().objectName() == 'card' else self
        added_height = self.end_height - self.start_height + self.toggle.sizeHint().height() + self.layout().spacing()
        center = card.mapTo(parent.widget(), QPoint(0, card.height() // 2)).y() + added_height // 2
        bar = parent.verticalScrollBar()
        self.scroll_start = bar.value()
        if not self.description.expanded:
            # Follow the shrinking range instead of letting Qt clamp it in jumps.
            shrinking = self.end_height - self.start_height - self.toggle.sizeHint().height() - self.layout().spacing()
            self.scroll_target = max(bar.minimum(), min(bar.value(), bar.maximum() + shrinking))
            return
        self.scroll_target = max(bar.minimum(), min(bar.maximum() + added_height,
                                center - parent.viewport().height() // 2))

    def animate_frame(self, value):
        self.description.setFixedHeight(round(value))
        distance = self.end_height - self.start_height
        progress = (value - self.start_height) / distance if distance else 1
        if not self.description.expanded:
            self.toggle.setFixedHeight(max(0, round(self.button_start_height * (1 - progress))))
        if self.page_scroll is None:
            return
        # Reflow first so the growing page's scroll range follows this frame.
        parent = self.description.parentWidget()
        while parent is not None and parent is not self.page_scroll:
            if parent.layout() is not None:
                parent.layout().activate()
            parent = parent.parentWidget()
        distance = self.end_height - self.start_height
        progress = (value - self.start_height) / distance if distance else 1
        position = self.scroll_start + (self.scroll_target - self.scroll_start) * progress
        self.page_scroll.verticalScrollBar().setValue(round(position))
