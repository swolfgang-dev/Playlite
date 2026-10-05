from .theme import colour, set_style
from .theme import apply as apply_theme, themed_asset
from .lifecycle import show_warning
from .lifecycle import run_dialog
import argparse
import html
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .editor import MetadataEditor, save_game
from .artwork import repair_artwork
from .ui_style import DROPDOWN_STYLE
from .library import FILTER_FIELDS, SORT_FIELDS, query_games, values
from .scroll_fades import ScrollFades, HorizontalValuesScroll
from .link_names import load_names, friendly_name

from PyQt6.QtCore import QAbstractAnimation, QItemSelectionModel, Qt, QSize, QUrl, QTimer, QRect, QRectF, QSettings, QThreadPool, QEvent, QVariantAnimation, QEasingCurve, QElapsedTimer
from PyQt6.QtGui import QFontMetrics, QColor, QDesktopServices, QIcon, QImage, QImageReader, QCursor, QPainter, QPen, QPainterPath, QPixmap, QTextDocument, QRegion
from PyQt6.QtWidgets import (
    QApplication, QAbstractItemView, QStyledItemDelegate, QStyleOptionViewItem, QStyle, QDialog, QDialogButtonBox, QFormLayout, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSplitter, QTextBrowser, QTextEdit,
    QVBoxLayout, QBoxLayout, QWidget, QComboBox, QCheckBox, QGridLayout, QListView, QMenu, QAbstractItemView,
)

DATA = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'playlite'
STYLE = '''
QToolTip { background: #242527; color: #e9e9e9; border: 1px solid #62646a; border-radius: 6px; padding: 8px 12px; font-size: 13px; }
QWidget { background: #101112; color: #e9e9e9; font-family: "DejaVu Sans"; font-size: 13px; }
QMainWindow, QWidget#toolbar { background: #171819; }
QWidget#rail { background: #151617; border-right: 1px solid #252628; }
QLabel { background: transparent; }
QLabel#brand { color: #dc69a1; font-weight: bold; font-size: 22px; }
QLineEdit { background: #2c2d2f; border: 0; border-radius: 15px; padding: 8px 13px; }
QListWidget { border: 0; background: #141516; outline: 0; padding: 8px; font-size: 15px; }
QListWidget::item { padding: 8px; border-radius: 7px; }
QListWidget::item:selected { background: #292a2c; }
QListWidget::item:hover { background: #222325; }
QScrollArea { border: 0; }
QWidget#qt_scrollarea_vcontainer,
QWidget#qt_scrollarea_hcontainer { background: transparent; }
QAbstractScrollArea::corner { background: transparent; }
QFrame#card { background: #1d1e20; border-radius: 16px; }
QWidget#content, QWidget#page { background: transparent; }
QTextBrowser { border: 0; background: transparent; color: #e9e9e9; }
QTextBrowser#description { border: 0; background: transparent; }
QScrollBar:vertical { background: transparent; width: 24px; margin: 0 8px; }
QScrollBar::handle:vertical { background: #414246; min-height: 25px; border-radius: 4px; }
QScrollBar::groove:vertical { background: transparent; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: transparent; height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 24px; margin: 8px 0; }
QScrollBar::handle:horizontal { background: #414246; min-width: 25px; border-radius: 4px; }
QScrollBar::groove:horizontal { background: transparent; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { background: transparent; width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QPushButton { background: #363638; border: 0; border-radius: 7px; padding: 10px 18px; }
QPushButton:hover { background: #48494b; }
QPushButton#logo, QPushButton#logo:hover, QPushButton#logo:pressed {
    background: transparent; border: 0; padding: 0;
}
QPushButton#logo::menu-indicator { image: none; width: 0; height: 0; }
QMenu { background: #242527; border: 1px solid #404144; border-radius: 8px; padding: 6px; }
QMenu::item { padding: 10px 22px; border-radius: 5px; }
QMenu::item:selected { background: #3b3d41; }
QMenu::separator { height: 1px; background: #404144; margin: 5px 8px; }
QPushButton:checked { background: #48494b; }
QPushButton#sortOrder:checked { background: #363638; }
QPushButton#sortOrder:checked:hover { background: #48494b; }
QPushButton#filters[activeFilter="true"] { background: #48494b; }
QPushButton#play { background: #f0f0f0; color: #151515; font-weight: bold; }
QPushButton#play:hover { background: #ffffff; }
QPushButton:disabled { color: #777; background: #292a2b; }
QPushButton#link, QPushButton#folder { background: transparent; text-align: left; padding: 5px 0; }
QPushButton#link:hover, QPushButton#folder:hover { color: #98caff; }
QLabel#section { font-weight: bold; }
QLabel#muted { color: #999a9d; }
QSplitter::handle { background: #252628; width: 1px; }
QTextEdit { background: #2c2d2f; border: 1px solid #404144; border-radius: 6px; }
QComboBox { background: #2c2d2f; border: 0; border-radius: 6px; padding: 7px 10px; }
QComboBox QAbstractItemView { background: #242527; selection-background-color: #48494b; }
'''

STYLE += DROPDOWN_STYLE


def toolbar_icon(kind):
    names = {'ascending': 'view-sort-ascending', 'descending': 'view-sort-descending',
             'filters': 'view-filter', 'list': 'view-list-details', 'grid': 'view-grid', 'compact': 'view-list-icons'}
    themed = QIcon.fromTheme(names[kind])
    if kind not in ('list', 'grid', 'compact') and not themed.isNull():
        return themed
    pixmap = QPixmap(48, 48)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(colour('#e9e9e9')), 1.8))
    if kind == 'grid':
        for x in (4, 14):
            for y in (4, 14):
                painter.drawRect(x, y, 6, 6)
    elif kind == 'compact':
        for y in (5, 12, 19):
            painter.drawEllipse(9, y - 2, 4, 4)
    elif kind == 'list':
        for y in (5, 12, 19):
            painter.drawPoint(4, y)
            painter.drawLine(9, y, 21, y)
    elif kind == 'filters':
        path = QPainterPath()
        path.moveTo(3, 4)
        for x, y in [(21, 4), (14, 12), (14, 20), (10, 18), (10, 12), (3, 4)]:
            path.lineTo(x, y)
        painter.drawPath(path)
    else:
        painter.drawLine(17, 4, 17, 20)
        y, end = (4, 8) if kind == 'ascending' else (20, 16)
        painter.drawLine(17, y, 13, end)
        painter.drawLine(17, y, 21, end)
        for index in range(3):
            painter.drawLine(3, 5 + index * 7, 5 + index * 3, 5 + index * 7)
    painter.end()
    return QIcon(pixmap)


class ArtworkPage(QWidget):
    def __init__(self):
        super().__init__()
        self.background = QPixmap()
        self.rendered_background = QPixmap()
        self.defer_background_render = False

    def set_background(self, source, blur_radius=48):
        self.background_generation = getattr(self, 'background_generation', 0) + 1
        generation = self.background_generation
        self.background = QPixmap()
        self.rendered_background = QPixmap()
        self.update()
        if isinstance(source, QPixmap):
            if source.isNull():
                return
            source = source.toImage()
            key = None
        else:
            path = Path(source)
            if not path.is_file():
                return
            key = (str(path), path.stat().st_mtime_ns, blur_radius, colour('#101112'))
        self.background_cache = getattr(self, 'background_cache', {})
        if key is not None and key in self.background_cache:
            self.background = self.background_cache[key]
            self.update()
            return
        from .metadata_dialog import Task
        from .background_art import prepare
        base = colour('#101112')
        task = Task(lambda: prepare(source, blur_radius, base))
        self.background_tasks = getattr(self, 'background_tasks', [])
        self.background_tasks.append(task)
        def complete(image):
            from PyQt6 import sip
            if sip.isdeleted(self):
                self.background_tasks.remove(task)
                return
            pixmap = QPixmap.fromImage(image)
            if key is not None:
                if len(self.background_cache) >= 12:
                    self.background_cache.pop(next(iter(self.background_cache)))
                self.background_cache[key] = pixmap
            if generation == self.background_generation:
                self.background = pixmap
                self.update()
            self.background_tasks.remove(task)
        def failed(error):
            self.background_tasks.remove(task)
        task.signals.succeeded.connect(complete)
        task.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(task)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.background.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # Draw the cached image directly; resize animations never regenerate it.
        source = self.background.rect()
        aspect = self.width() / max(1, self.height())
        image_aspect = source.width() / max(1, source.height())
        if image_aspect > aspect:
            width = round(source.height() * aspect)
            source.setX((source.width() - width) // 2)
            source.setWidth(width)
        else:
            height = round(source.width() / aspect)
            source.setY((source.height() - height) // 2)
            source.setHeight(height)
        painter.drawPixmap(self.rect(), self.background, source)


def game_context_menu(parent, edit_handler, delete_handler, plugin_actions=()):
    menu = QMenu(parent)
    if edit_handler is not None:
        menu.addAction('Edit…').triggered.connect(edit_handler)
    menu.addSeparator()
    for plugin_name, actions in plugin_actions:
        if actions:
            submenu = menu.addMenu(plugin_name)
            for title, callback in actions:
                submenu.addAction(title).triggered.connect(callback)
    menu.addSeparator()
    menu.addAction('Delete…').triggered.connect(delete_handler)
    return menu


class Hero(QWidget):
    def __init__(self, play, edit_handler, delete_handler, plugin_actions=()):
        super().__init__()
        self.pixmap = QPixmap()
        self.header_offset = 0.5
        self.setFixedHeight(360)
        control = QWidget(self)
        self.play_control = control
        self.play_button = play
        control.setObjectName('playControl')
        set_style(control, 'QWidget#playControl { background: transparent; }')
        control.setFixedWidth(150)
        split = QHBoxLayout(control)
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(0)
        set_style(play, 'border-top-right-radius: 0; border-bottom-right-radius: 0;')
        split.addWidget(play, 1)
        dropdown = QPushButton()
        dropdown.setIcon(QIcon(themed_asset(Path(__file__).parent / 'assets' / 'chevron-down-dark.svg')))
        dropdown.setIconSize(QSize(14, 14))
        button_height = play.sizeHint().height()
        control.setFixedHeight(button_height)
        play.setFixedHeight(button_height)
        dropdown.setFixedHeight(button_height)
        dropdown.setFixedWidth(30)
        dropdown.setToolTip('Game actions')
        dropdown.setAccessibleName('Game actions')
        set_style(dropdown, 'QPushButton { background: #f0f0f0; color: #151515; padding: 10px 0; border-left: 1px solid #cccccc; border-top-left-radius: 0; border-bottom-left-radius: 0; } QPushButton:hover { background: white; } QPushButton::menu-indicator { image: none; width: 0; }')
        menu = game_context_menu(dropdown, edit_handler, delete_handler, plugin_actions)
        dropdown.setMenu(menu)
        split.addWidget(dropdown)
        self.position_play_control()

    def align_with_cover(self, cover_width):
        self.position_play_control()

    def position_play_control(self):
        padding = 8 if self.pixmap.isNull() else 24
        self.play_control.setFixedWidth(max(150, self.play_button.sizeHint().width() + 30))
        self.play_control.layout().activate()
        self.play_control.move(padding, max(padding, self.height() - self.play_control.height() - padding))
        self.update()
        self.play_control.show()
        self.play_control.raise_()

    def showEvent(self, event):
        super().showEvent(event)
        self.position_play_control()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.pixmap.isNull():
            # Fit the complete image until the pane is too narrow for a useful height.
            height = max(240, round(self.width() * self.pixmap.height() / self.pixmap.width()))
            if self.height() != height:
                self.setFixedHeight(height)
            if height > 240:
                self.header_offset = .5
        self.position_play_control()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0., 0., float(self.width()), float(self.height()), 20., 20.)
        painter.setClipPath(clip)
        if not self.pixmap.isNull():
            painter.fillRect(self.rect(), QColor(colour('#292a2d')))
            ratio = self.devicePixelRatioF()
            pixels = QSize(round(self.width() * ratio), round(self.height() * ratio))
            scaled = self.pixmap.scaled(pixels, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                        Qt.TransformationMode.SmoothTransformation)
            scaled.setDevicePixelRatio(ratio)
            logical = scaled.deviceIndependentSize()
            painter.drawPixmap(-round((logical.width() - self.width()) * self.header_offset),
                               round((self.height() - logical.height()) / 2), scaled)
        # Paint the shadow in the header; child graphics effects can lose their
        # cached button rendering when the detail pane is rebuilt or resized.
        # Match the offset to the blur spread so it cannot extend above or left.
        shadow_rect = QRectF(self.play_control.geometry()).translated(6, 6)
        painter.setPen(Qt.PenStyle.NoPen)
        for spread in range(6, -1, -1):
            shadow = QColor(colour('#000000'))
            shadow.setAlpha(8 if spread else 35)
            painter.setBrush(shadow)
            painter.drawRoundedRect(shadow_rect.adjusted(-spread, -spread, spread, spread),
                                    8 + spread, 8 + spread)

    def wheelEvent(self, event):
        if self.pixmap.isNull():
            event.ignore()
            return
        scale = max(self.width() / self.pixmap.width(), self.height() / self.pixmap.height())
        overflow = self.pixmap.width() * scale - self.width()
        if overflow <= 0:
            event.ignore()
            return
        pixels, angles = event.pixelDelta(), event.angleDelta()
        delta = pixels.x() or pixels.y() or (angles.x() or angles.y()) / 120 * 80
        self.header_offset = max(0, min(1, self.header_offset - delta / overflow))
        self.update()
        event.accept()


def label(text, role=None):
    widget = QLabel(text)
    widget.setWordWrap(True)
    if role:
        widget.setObjectName(role)
    return widget


def card():
    frame = QFrame()
    frame.setObjectName('card')
    frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(12)
    return frame, layout


class Description(QTextBrowser):
    def __init__(self, content):
        super().__init__()
        self.setObjectName('description')
        self.setOpenExternalLinks(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.fades = ScrollFades(self)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.document().setDocumentMargin(0)
        self.setHtml(content)

    def wheelEvent(self, event):
        bar = self.verticalScrollBar()
        if bar.maximum() <= bar.minimum():
            event.ignore()
            return
        super().wheelEvent(event)
        event.accept()


def horizontal_values(values, role=None, on_click=None, separator=', '):
    text = QLabel(separator.join(values))
    if on_click is not None:
        color = colour('#999a9d') if role == 'muted' else colour('#e9e9e9')
        text.setText(separator.join(f'<a href="{index}" style="color: {color}; text-decoration: none;">{html.escape(str(value))}</a>' for index, value in enumerate(values)))
        text.linkActivated.connect(lambda index: on_click(values[int(index)]))
    if role:
        text.setObjectName(role)
    text.setWordWrap(False)
    text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | (Qt.TextInteractionFlag.LinksAccessibleByMouse if on_click else Qt.TextInteractionFlag.NoTextInteraction))
    text.setContentsMargins(0, 0, 0, 0)
    text.adjustSize()
    area = HorizontalValuesScroll()
    set_style(area, 'QScrollArea, QScrollArea > QWidget, QScrollArea QLabel { background: transparent; border: 0; }')
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.viewport().setAutoFillBackground(False)
    set_style(text, 'background: transparent;')
    area.setWidget(text)
    area.setWidgetResizable(False)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setFixedHeight(text.sizeHint().height())
    area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    area.fades = ScrollFades(area, horizontal=True)
    return area


class LinkLayout(QLayout):
    """Use the panel width while keeping wrapped links left aligned."""
    def __init__(self, vertical=False):
        super().__init__()
        self.vertical = vertical
        self.items = []
        self.separators = []
        self.row_spacing = None
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(18)

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    def expandingDirections(self):
        return Qt.Orientation.Horizontal

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.arrange(QRect(0, 0, width, 0), False)

    def minimumSize(self):
        return QSize(0,
                     max((i.minimumSize().height() for i in self.items), default=0))

    def sizeHint(self):
        return self.minimumSize()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.arrange(rect, True)

    def arrange(self, rect, apply):
        rows, row, used = [], [], 0
        width = max(1, rect.width())
        for item in self.items:
            size = item.sizeHint()
            needed = min(width, size.width())
            if row and (self.vertical or used + self.spacing() + needed > width):
                rows.append(row)
                row, used = [], 0
            used += (self.spacing() if row else 0) + needed
            height = item.heightForWidth(needed) if item.hasHeightForWidth() else size.height()
            row.append((item, needed, height))
        if row:
            rows.append(row)
        y = rect.y()
        row_spacing = self.spacing() if self.row_spacing is None else self.row_spacing
        if apply:
            self.separators = []
        for row in rows:
            height = max(entry[2] for entry in row)
            x = rect.x()
            for index, (item, cell_width, _) in enumerate(row):
                if apply:
                    item.setGeometry(QRect(x, y, cell_width, height))
                    if index:
                        self.separators.append(QRect(x - self.spacing(), y, self.spacing(), height))
                x += cell_width + self.spacing()
            y += height + row_spacing
        return y - rect.y() - (row_spacing if rows else 0)


class LinkContent(QWidget):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QColor(colour('secondary_text')))
        for rect in self.layout().separators:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, '·')


class LinksScroll(QScrollArea):
    def __init__(self, content, flow):
        super().__init__()
        self.flow = flow
        self.setWidget(content)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        set_style(self, 'QScrollArea, QScrollArea > QWidget { background: transparent; border: 0; }')
        self.viewport().setAutoFillBackground(False)
        self.fades = ScrollFades(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_rows()

    def fit_rows(self):
        full_height = self.flow.heightForWidth(max(1, self.viewport().width()))
        self.widget().setMinimumHeight(full_height)
        row = self.parentWidget().parentWidget() if self.parentWidget() else None
        if isinstance(row, DescriptionLinksRow) and not row.wide:
            row.update_links_height()

    def wheelEvent(self, event):
        bar = self.verticalScrollBar()
        delta = event.pixelDelta().y() or event.angleDelta().y()
        if (bar.maximum() <= bar.minimum() or not delta
                or (delta > 0 and bar.value() <= bar.minimum())
                or (delta < 0 and bar.value() >= bar.maximum())):
            event.ignore()
            return
        super().wheelEvent(event)


class RevealPanel(QWidget):
    """Clip a stable control layout instead of compressing it every frame."""
    def __init__(self):
        super().__init__()
        self.content = QWidget(self)

    def sizeHint(self):
        return self.content.sizeHint()

    def minimumSizeHint(self):
        return QSize(0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.content.setGeometry(0, 0, self.width(), self.content.sizeHint().height())


class ResponsiveContent(QWidget):
    columns_breakpoint = 620

    def __init__(self):
        super().__init__()
        self.cover = None
        self.animated_cover = None
        self.cover_visible = None
        self.description_links_row = None
        self.installation_row = None
        self.cover_animation = QVariantAnimation(self)
        self.cover_animation.setDuration(320)
        self.cover_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.cover_animation.valueChanged.connect(self.animate_cover)
        self.cover_animation.finished.connect(self.finish_cover)

    def animate_cover(self, value):
        if self.cover is self.animated_cover and self.cover is not None:
            self.cover.setFixedWidth(round(value))

    def finish_cover(self):
        if self.cover is self.animated_cover and self.cover is not None:
            self.cover.setVisible(self.cover_visible)

    def minimumSizeHint(self):
        return QSize(0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_cover()

    def update_cover(self):
        visible = self.width() >= self.columns_breakpoint
        if self.description_links_row is not None:
            self.description_links_row.set_columns(visible)
        if self.installation_row is not None:
            self.installation_row.set_columns(visible)
        if self.cover is None:
            return
        if self.cover is not self.animated_cover:
            self.cover_animation.stop()
            self.animated_cover = self.cover
            self.cover_width = self.cover.width()
            self.cover_visible = visible
            self.cover.setVisible(visible)
            self.cover.setFixedWidth(self.cover_width if visible else 0)
            return
        if visible == self.cover_visible:
            return
        self.cover_visible = visible
        self.cover_animation.stop()
        if not self.isVisible() or not getattr(self.window(), 'toolbar_launch_settled', False) or getattr(self.window(), 'switching_library_view', False):
            self.cover.setFixedWidth(self.cover_width if visible else 0)
            self.cover.setVisible(visible)
            return
        start = self.cover.width()
        self.cover.show()
        self.cover_animation.blockSignals(True)
        self.cover_animation.setStartValue(float(start))
        self.cover_animation.setEndValue(float(self.cover_width if visible else 0))
        self.cover_animation.blockSignals(False)
        self.cover_animation.start()


class DescriptionLinksRow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName('descriptionLinksRow')
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.columns = QHBoxLayout(self)
        self.columns.setContentsMargins(0, 0, 0, 0)
        self.columns.setSpacing(24)
        self.links = None
        self.links_size = QSize()
        self.description = None
        self.link_scroll = None
        self.wide = None

    def set_columns(self, wide):
        if self.wide == wide:
            return
        self.wide = wide
        self.columns.setDirection(QBoxLayout.Direction.LeftToRight if wide
                                  else QBoxLayout.Direction.TopToBottom)
        if self.links is not None:
            self.link_scroll.flow.vertical = wide
            self.link_scroll.flow.invalidate()
            self.link_scroll.fit_rows()
            if wide:
                self.links.setFixedWidth(self.links_size.width())
            else:
                self.links.setMinimumWidth(0)
                self.links.setMaximumWidth(16777215)
            self.update_links_height()

    def update_links_height(self):
        if self.links is None or self.link_scroll is None:
            return
        if self.wide and self.description is not None:
            self.link_scroll.setMinimumHeight(0)
            self.link_scroll.setMaximumHeight(16777215)
            self.links.setFixedHeight(self.description.height())
        else:
            height = max(1, self.link_scroll.flow.heightForWidth(max(1, self.link_scroll.viewport().width())))
            self.link_scroll.setFixedHeight(height)
            layout = self.links.layout()
            margins = layout.contentsMargins()
            heading = layout.itemAt(0).widget()
            self.links.setFixedHeight(margins.top() + margins.bottom() + heading.sizeHint().height()
                                      + layout.spacing() + height)

    def eventFilter(self, watched, event):
        if watched is self.description and event.type() == QEvent.Type.Resize:
            self.update_links_height()
        return super().eventFilter(watched, event)


def selection_border(painter, rect):
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(colour('accent')), 2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), 7, 7)
    painter.restore()


class CompactLibraryDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        view = self.parent()
        if view.viewMode() != QListView.ViewMode.ListMode:
            super().paint(painter, option, index)
            if option.state & QStyle.StateFlag.State_Selected and view.has_multiple_selection():
                selection_border(painter, option.rect)
            return
        if index.data(Qt.ItemDataRole.DisplayRole) or view.width_transition:
            decorated = QStyleOptionViewItem(option)
            self.initStyleOption(decorated, index)
            if view.width_transition:
                decorated.text = (index.data(Qt.ItemDataRole.UserRole) or {}).get('Name', '')
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setClipRect(option.rect)
            if option.state & (QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver):
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(view.row_surface())
                painter.drawRoundedRect(QRectF(option.rect), 7, 7)
            if option.state & QStyle.StateFlag.State_Selected and view.has_multiple_selection():
                selection_border(painter, option.rect)
            icon_slot = QRect(option.rect)
            icon_slot.setWidth(64)
            icon_rect = QRect(0, 0, view.iconSize().width(), view.iconSize().height())
            icon_rect.moveCenter(icon_slot.center())
            decorated.icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter,
                                 QIcon.Mode.Normal, QIcon.State.Off)
            text_rect = option.rect.adjusted(64, 0, -8, 0)
            metrics = QFontMetrics(decorated.font)
            offset = view.title_offset(index.data(Qt.ItemDataRole.UserRole), text_rect.width(), metrics)
            painter.setClipRect(text_rect)
            painter.setFont(decorated.font)
            painter.setPen(QColor(colour('#e9e9e9')))
            text = decorated.text
            if offset is None:
                text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width())
            else:
                text_rect.translate(-round(offset), 0)
                text_rect.setWidth(metrics.horizontalAdvance(text) + 2)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            painter.restore()
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = False  # Hover highlight is revealed by the row animation.
        game = index.data(Qt.ItemDataRole.UserRole) or {}
        row_width = 64
        row_rect = QRect(option.rect)
        row_rect.setWidth(round(row_width))
        painter.setClipRect(row_rect)
        if (selected or hovered or row_width > 64) and view.row_widths.get(game.get('Id'), 0) <= 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(view.row_surface())
            painter.drawRoundedRect(row_rect, 7, 7)
            if selected and view.has_multiple_selection():
                selection_border(painter, row_rect)
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if icon is not None and view.row_widths.get(game.get('Id'), 64) <= 64:
            size = view.iconSize()
            rect = QRect(0, 0, size.width(), size.height())
            base = QRect(option.rect)
            base.setWidth(64)
            rect.moveCenter(base.center())
            icon.paint(painter, rect, Qt.AlignmentFlag.AlignCenter, QIcon.Mode.Normal, QIcon.State.Off)
        painter.setFont(option.font)
        painter.setPen(QColor(colour('#e9e9e9')))
        text_rect = QRect(option.rect)
        text_rect.setLeft(text_rect.left() + 64)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, game.get('Name', ''))
        painter.restore()


class LibraryRowExpansion(QWidget):
    def __init__(self, view):
        super().__init__(view.window())
        self.view = view
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        set_style(self, 'background: transparent;')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.view.font())
        for index in range(self.view.count()):
            item = self.view.item(index)
            game = item.data(Qt.ItemDataRole.UserRole)
            width = self.view.row_widths.get(game['Id'], 0)
            if width <= 0:
                continue
            row = self.view.visualItemRect(item)
            if not self.view.viewport().rect().intersects(row):
                continue
            origin = self.view.viewport().mapTo(self, row.topLeft())
            rect = QRect(origin, QSize(round(width), row.height()))
            icon = QRect(origin.x() + 8, origin.y() + (row.height() - 48) // 2, 48, 48)
            path = QPainterPath()
            path.addRoundedRect(float(rect.x()), float(rect.y()), float(rect.width()), float(rect.height()), 7, 7)
            painter.save()
            painter.setClipPath(path)
            painter.fillPath(path, self.view.row_surface())
            item.icon().paint(painter, icon, Qt.AlignmentFlag.AlignCenter, QIcon.Mode.Normal, QIcon.State.Off)
            painter.setPen(QColor(colour('#e9e9e9')))
            text = QRect(rect)
            text.setLeft(rect.left() + 64)
            painter.setClipRect(text, Qt.ClipOperation.IntersectClip)
            animation = self.view.row_animations.get(game['Id'])
            available = (animation.endValue() if animation and animation.endValue() > 0 else width) - 76
            offset = self.view.title_offset(game, available) or 0
            text.translate(-round(offset), 0)
            text.setWidth(self.view.fontMetrics().horizontalAdvance(game['Name']) + 2)
            painter.drawText(text, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, game['Name'])
            painter.restore()
            if item.isSelected() and self.view.has_multiple_selection():
                selection_border(painter, rect)


class LibraryList(QListWidget):
    def has_multiple_selection(self):
        return len(self.selectedItems()) > 1

    def row_surface(self):
        return QColor(colour('#292a2c'))

    def __init__(self):
        super().__init__()
        self.balancing_grid = False
        self.grid_signature = None
        self.row_widths = {}
        self.row_animations = {}
        self.hover_id = None
        self.title_clock = QElapsedTimer()
        self.title_timer = QTimer(self)
        self.title_timer.setInterval(16)
        self.title_timer.timeout.connect(self.refresh_title_animation)
        self.scrollbar_padding = None
        self.panel_transparency = 0
        self.compact_enabled = False
        self.width_transition = False
        self.gutter_animation = QVariantAnimation(self)
        self.gutter_animation.setDuration(220)
        self.gutter_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.gutter_animation.valueChanged.connect(lambda value: self.setFixedWidth(round(value)))
        self.gutter_animation.stateChanged.connect(self.update_animation_scrollbar)
        self.gutter_animation.finished.connect(self.finish_gutter_animation)
        self.expansion_layer = None
        self.setMouseTracking(True)
        self.setItemDelegate(CompactLibraryDelegate(self))
        set_style(self, 'QListWidget { padding: 8px; } QListWidget[compactRail="true"] { padding-right: 0; } QListWidget > QWidget#qt_scrollarea_viewport, QListWidget > QWidget#qt_scrollarea_vcontainer, QListWidget > QWidget#qt_scrollarea_hcontainer { background: transparent; } QScrollBar:vertical { background: transparent; width: 24px; margin: 0 8px 0 8px; } QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }')
        self.verticalScrollBar().valueChanged.connect(self.refresh_hover)
        self.verticalScrollBar().rangeChanged.connect(self.update_scrollbar_padding)
        self.currentItemChanged.connect(self.update_selected_row)
        self.itemSelectionChanged.connect(self.update_selected_rows)

    def update_selected_row(self, current, previous):
        if not self.compact_enabled:
            return
        if previous:
            game_id = previous.data(Qt.ItemDataRole.UserRole)['Id']
            if game_id != self.hover_id and self.row_widths.get(game_id, 0) > 0:
                self.animate_row(game_id, 0)

    def update_selected_rows(self):
        if self.compact_enabled:
            multiple = self.has_multiple_selection()
            for index in range(self.count()):
                game_id = self.item(index).data(Qt.ItemDataRole.UserRole)['Id']
                if game_id != self.hover_id and (multiple and self.item(index).isSelected()
                        or self.row_widths.get(game_id, 0) > 0 or game_id in self.row_animations):
                    self.animate_row(game_id, 0)
        self.viewport().update()
        if self.expansion_layer is not None:
            self.expansion_layer.update()

    def title_offset(self, game, available, metrics=None):
        if not game or game.get('Id') != self.hover_id or not self.title_clock.isValid():
            return None
        metrics = metrics or self.fontMetrics()
        overflow = metrics.horizontalAdvance(game['Name']) + 2 - max(1, available)
        if overflow <= 0:
            return None
        # Pause at each end, then scroll at a steady readable speed.
        travel = overflow / 45
        phase = (self.title_clock.elapsed() / 1000) % (2 * travel + 1.6)
        if phase < .8:
            return 0
        if phase < .8 + travel:
            return (phase - .8) * 45
        if phase < 1.6 + travel:
            return overflow
        return max(0, overflow - (phase - 1.6 - travel) * 45)

    def refresh_title_animation(self):
        self.viewport().update()
        if self.expansion_layer is not None:
            self.expansion_layer.update()

    def update_scrollbar_padding(self, *_):
        previous_gutter = self.scrollbar_padding
        self.scrollbar_padding = self.verticalScrollBar().sizeHint().width() if self.verticalScrollBar().maximum() > 0 else 0
        right_padding = 0 if self.scrollbar_padding else 8
        left_padding = 8
        alpha = round(255 * (1 - self.panel_transparency / 100))
        style = f'QListWidget {{ background: rgba(20, 21, 22, {alpha}); padding: 8px; padding-left: {left_padding}px; padding-right: {right_padding}px; }} QListWidget > QWidget#qt_scrollarea_viewport, QListWidget > QWidget#qt_scrollarea_vcontainer, QListWidget > QWidget#qt_scrollarea_hcontainer {{ background: transparent; }} QScrollBar:vertical {{ background: transparent; width: 24px; margin: 0 8px 0 8px; }} QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}'
        style += ' QListWidget::item:selected, QListWidget::item:hover { background: #292a2c; }'
        if self.styleSheet() != style:
            set_style(self, style)
        self.fit_compact_width()
        if previous_gutter is not None and previous_gutter != self.scrollbar_padding and self.viewMode() == QListView.ViewMode.IconMode:
            previous_space = max(0, previous_gutter - 8)
            current_space = max(0, self.scrollbar_padding - 8)
            previous_target = self.gutter_animation.endValue() if self.gutter_animation.state() == QAbstractAnimation.State.Running else self.width()
            target = previous_target + current_space - previous_space
            self.gutter_animation.stop()
            self.gutter_animation.blockSignals(True)
            self.gutter_animation.setStartValue(float(self.width()))
            self.gutter_animation.setEndValue(float(target))
            self.gutter_animation.blockSignals(False)
            if self.isVisible() and getattr(self.window(), 'toolbar_launch_settled', False) and not getattr(self.window(), 'switching_library_view', False):
                self.gutter_animation.start()
            else:
                self.setFixedWidth(target)
                self.finish_gutter_animation()
        if previous_gutter != self.scrollbar_padding and not self.balancing_grid:
            QTimer.singleShot(0, self.balance_grid)

    def compact_width(self):
        # 64px icon tile plus 8px on each side; a scrollbar replaces the right pad.
        return (72 + self.scrollbar_padding if self.scrollbar_padding else 80) + 2 * self.spacing()

    def update_animation_scrollbar(self, *_):
        window = self.window()
        if hasattr(window, 'update_library_scrollbar_policy'):
            window.update_library_scrollbar_policy()

    def finish_gutter_animation(self):
        if self.viewMode() == QListView.ViewMode.IconMode and not self.width_transition:
            self.setMinimumWidth(160)
            self.setMaximumWidth(16777215)
        self.update_animation_scrollbar()

    def fit_compact_width(self):
        if self.compact_enabled and not self.width_transition:
            target = self.compact_width()
            if self.gutter_animation.endValue() != target:
                start = self.width()
                self.gutter_animation.stop()
                self.gutter_animation.blockSignals(True)
                self.gutter_animation.setStartValue(float(start))
                self.gutter_animation.setEndValue(float(target))
                self.gutter_animation.blockSignals(False)
                if self.isVisible() and getattr(self.window(), 'toolbar_launch_settled', False) and not getattr(self.window(), 'switching_library_view', False):
                    self.gutter_animation.start()
                else:
                    self.setFixedWidth(target)
        if self.expansion_layer is not None:
            self.expansion_layer.setGeometry(self.window().rect())
            self.expansion_layer.setVisible(self.compact_enabled and any(width > 0 for width in self.row_widths.values()))
            self.expansion_layer.raise_()
            self.expansion_layer.update()
        self.viewport().update()

    def expanded_row_width(self, game):
        width = 64 + self.fontMetrics().horizontalAdvance(game['Name']) + 14
        return min(width, max(64, self.window().width() - 250))

    def animate_row(self, game_id, target):
        current = self.currentItem()
        selected = next((item for item in self.selectedItems() if item.data(Qt.ItemDataRole.UserRole)['Id'] == game_id), None)
        if target == 0:
            if selected is not None and self.has_multiple_selection():
                target = self.expanded_row_width(selected.data(Qt.ItemDataRole.UserRole))
            elif selected is not None or current and current.data(Qt.ItemDataRole.UserRole)['Id'] == game_id:
                target = 64
        if self.expansion_layer is None:
            self.expansion_layer = LibraryRowExpansion(self)
        animation = self.row_animations.get(game_id)
        if animation is None:
            animation = QVariantAnimation(self)
            animation.setEasingCurve(QEasingCurve.Type.Linear)
            def changed(value):
                self.row_widths[game_id] = value
                self.fit_compact_width()
            animation.valueChanged.connect(changed)
            self.row_animations[game_id] = animation
        if animation.endValue() == target:
            return
        start_width = float(self.row_widths.get(game_id, 0))
        if target == 64:
            start_width = max(64, start_width)
        animation.stop()
        # Reconfiguring a finished animation can emit its old endpoint.
        # Preserve the visible width and reset its clock before starting.
        animation.blockSignals(True)
        animation.setCurrentTime(0)
        animation.setDuration(250 if target > start_width else 1000)
        animation.setStartValue(start_width)
        animation.setEndValue(float(target))
        animation.blockSignals(False)
        self.row_widths[game_id] = start_width
        animation.start()

    def hide_hover_immediately(self, preserve_selected=False):
        self.title_timer.stop()
        for animation in self.row_animations.values():
            animation.stop()
            animation.deleteLater()
        self.row_animations.clear()
        self.row_widths.clear()
        self.hover_id = None
        if preserve_selected and self.compact_enabled and self.has_multiple_selection():
            for item in self.selectedItems():
                game = item.data(Qt.ItemDataRole.UserRole)
                self.row_widths[game['Id']] = self.expanded_row_width(game)
        self.fit_compact_width()

    def refresh_hover(self):
        self.update_hover(self.viewport().mapFromGlobal(QCursor.pos()))

    def update_hover(self, position):
        item = self.itemAt(position) if self.viewport().rect().contains(position) else None
        game = item.data(Qt.ItemDataRole.UserRole) if item and self.viewMode() == QListView.ViewMode.ListMode else None
        game_id = game['Id'] if game else None
        if game_id == self.hover_id:
            return
        if self.hover_id is not None and self.compact_enabled:
            self.animate_row(self.hover_id, 0)
        self.hover_id = game_id
        if game:
            self.title_clock.start()
            self.title_timer.start()
        else:
            self.title_timer.stop()
        self.viewport().update()
        if game and self.compact_enabled:
            # Include the same 2px text slack used by title_offset.
            self.animate_row(game_id, self.expanded_row_width(game))

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.update_hover(event.position().toPoint())

    def leaveEvent(self, event):
        if self.hover_id is not None and self.compact_enabled:
            self.animate_row(self.hover_id, 0)
        self.hover_id = None
        self.title_timer.stop()
        self.viewport().update()
        super().leaveEvent(event)

    def hideEvent(self, event):
        if hasattr(self, 'title_timer') and hasattr(self, 'expansion_layer'):
            self.hide_hover_immediately()
        super().hideEvent(event)

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip:
            event.accept()
            return True
        return super().viewportEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.balance_grid)

    def balance_grid(self):
        if self.viewMode() != QListView.ViewMode.IconMode or self.balancing_grid:
            return
        signature = (self.viewport().width(), self.spacing(), self.count())
        if signature == self.grid_signature and all(self.item(index).sizeHint() == self.gridSize() for index in range(self.count())):
            return
        self.grid_signature = signature
        self.balancing_grid = True
        try:
            width = max(1, self.viewport().width() - 2 * self.spacing())
            columns = max(1, width // 180)
            cell_width = max(1, width // columns)
            # Check Qt's actual wrapping, which includes style-dependent icon padding.
            for candidate in range(cell_width, max(1, cell_width - 48), -1):
                size = QSize(candidate, 285)
                self.setGridSize(size)
                for index in range(self.count()):
                    if self.item(index).sizeHint() != size:
                        self.item(index).setSizeHint(size)
                self.doItemsLayout()
                if self.count() < columns or self.visualItemRect(self.item(columns - 1)).top() == self.visualItemRect(self.item(0)).top():
                    break
        finally:
            self.balancing_grid = False



class LibraryWindow(QMainWindow):
    def __init__(self, data):
        super().__init__()
        self.data = data
        from .providers import discover_plugins, GameProvider, GenericPlugin
        self.plugins = discover_plugins()
        self.game_providers = [plugin for plugin in self.plugins.values() if isinstance(plugin, GameProvider)]
        self.generic_plugins = [plugin for plugin in self.plugins.values() if isinstance(plugin, GenericPlugin)]
        self.settings = QSettings(str(data / 'ui.ini'), QSettings.Format.IniFormat)
        apply_theme(self.settings)
        if self.settings.value('app/resetSortingFilters', False, type=bool):
            for key in ('library/filters', 'library/sort', 'library/descending'):
                self.settings.remove(key)
        self.last_selected = self.settings.value('lastSelectedGame', '', type=str)
        self.games = json.loads((data / 'library.json').read_text()) if (data / 'library.json').exists() else []
        self.games = [repair_artwork(game, data) for game in self.games]
        if not self.games:
            self.setMinimumHeight(self.empty_library_height())
        self.current = None
        self.compact_library = False
        self.prefer_compact_library = self.settings.value('library/compact', False, type=bool)
        self.library_widths = {
            'list': self.settings.value('library/listWidth', 410, type=int),
            'grid': self.settings.value('library/gridWidth', 650, type=int),
        }
        self.thumbnail_cache = {}
        self.installation_sizes = {}
        self.size_tasks = []
        self.is_grid = self.settings.value('library/view', 'list') == 'grid'
        startup_view = self.settings.value('app/defaultView', 'remember')
        if startup_view != 'remember':
            self.is_grid = startup_view == 'grid'
            self.prefer_compact_library = startup_view == 'compact'
        try:
            self.active_filters = json.loads(self.settings.value('library/filters', '{}', type=str))
        except (ValueError, TypeError):
            self.active_filters = {}
        if not isinstance(self.active_filters, dict):
            self.active_filters = {}
        self.setWindowTitle('Playlite')
        screen = QApplication.primaryScreen()
        default_width = screen.availableGeometry().width() // 2 if screen else 1540
        self.fit_default_height = True
        size = QSize(default_width, 1140)
        self.resize(size)
        self.last_normal_size = QSize(size)
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        toolbar = QWidget()
        toolbar.setObjectName('toolbar')
        bar = QHBoxLayout(toolbar)
        self.toolbar_layout = bar
        self.toolbar_launch_settled = False
        self.library_animation = QVariantAnimation(self)
        self.library_animation.setDuration(320)
        self.library_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.library_animation.valueChanged.connect(self.animate_library_width)
        self.library_animation.finished.connect(self.finish_library_transition)
        bar.setContentsMargins(8, 12, 22, 12)
        self.logo = QPushButton()
        self.logo.setObjectName('logo')
        menu_art = QPixmap(str(Path(__file__).parent / 'assets' / 'playlite.png'))
        # The supplied icon has transparent margins; trim for the toolbar only.
        self.logo.setIcon(QIcon(menu_art.copy(13, 45, 231, 166)))
        self.logo.setIconSize(QSize(40, 40))
        self.logo.setFixedSize(48, 48)
        self.logo.setToolTip('Playlite menu')
        self.logo.setAccessibleName('Playlite menu')
        self.logo_menu = QMenu(self.logo)
        self.logo_menu.addAction('Add Game…').triggered.connect(self.add_game)
        self.logo_menu.addSeparator()
        self.logo_menu.addAction('Settings…').triggered.connect(self.open_settings)
        self.logo.setMenu(self.logo_menu)
        self.logo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.logo.customContextMenuRequested.connect(lambda position: self.logo_menu.popup(self.logo.mapToGlobal(position)))
        logo_slot = QWidget()
        logo_slot.setObjectName("logoSlot")
        set_style(logo_slot, "QWidget#logoSlot { background: transparent; }")
        logo_slot.setFixedWidth(64)
        logo_layout = QHBoxLayout(logo_slot)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignCenter)
        bar.addWidget(logo_slot)

        self.search = QLineEdit()
        self.search.setPlaceholderText('Search your library')
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(290)
        self.search.setMinimumWidth(140)
        self.search.textChanged.connect(self.filter_games)
        self.search.ensurePolished()
        control_height = self.search.sizeHint().height()
        self.search.setFixedHeight(control_height)
        logo_width = round(control_height * 231 / 166)
        self.logo.setFixedSize(logo_width, control_height)
        self.logo.setIconSize(QSize(logo_width, control_height))
        ratio = self.devicePixelRatioF()
        menu_icon = menu_art.copy(13, 45, 231, 166).scaled(
            round(logo_width * ratio), round(control_height * ratio),
            Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        menu_icon.setDevicePixelRatio(ratio)
        self.logo.setIcon(QIcon(menu_icon))
        bar.addWidget(self.search)
        self.sort = QComboBox()
        self.sort.setFixedHeight(control_height)
        set_style(self.sort, DROPDOWN_STYLE)
        for key, title in SORT_FIELDS:
            self.sort.addItem(title, key)
        saved_sort = self.settings.value('library/sort', 'Name')
        self.sort.setCurrentIndex(max(0, self.sort.findData(saved_sort)))
        self.sort.currentIndexChanged.connect(self.refresh_library)
        bar.addWidget(self.sort)
        self.order = QPushButton()
        self.order.setIcon(toolbar_icon('descending' if self.settings.value('library/descending', False, type=bool) else 'ascending'))
        self.order.setObjectName('sortOrder')
        self.order.setCheckable(True)
        self.order.setChecked(self.settings.value('library/descending', False, type=bool))
        self.order.setToolTip('Descending' if self.order.isChecked() else 'Ascending')
        self.order.clicked.connect(self.refresh_library)
        bar.addWidget(self.order)
        self.filter_button = QPushButton()
        self.filter_button.setIcon(toolbar_icon('filters'))
        self.filter_button.setToolTip('Filters')
        self.filter_button.setObjectName('filters')
        self.filter_button.setProperty('activeFilter', False)
        self.filter_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.filter_button.customContextMenuRequested.connect(lambda *_: self.reset_filters())
        bar.addWidget(self.filter_button)
        self.view = QComboBox(toolbar)
        self.view.hide()
        self.view.addItem('List view', 'list')
        self.view.addItem('Grid view', 'grid')
        self.view.setCurrentIndex(1 if self.is_grid else 0)
        self.view.currentIndexChanged.connect(self.change_view)
        self.view_buttons = {}
        for index, key, title in [(1, 'grid', 'Grid view'), (0, 'list', 'List view')]:
            button = QPushButton()
            button.setCheckable(True)
            button.setChecked(self.view.currentData() == key)
            button.setIcon(toolbar_icon(key))
            button.setToolTip(title)
            button.setAccessibleName(title)
            button.clicked.connect(lambda checked=False, index=index: self.select_view(index))
            self.view_buttons[key] = button
            bar.addWidget(button)
        self.compact_button = QPushButton()
        self.compact_button.setCheckable(True)
        self.compact_button.setChecked(self.prefer_compact_library)
        self.compact_button.setIcon(toolbar_icon('compact'))
        self.compact_button.setToolTip('Compact library list')
        self.compact_button.setAccessibleName('Compact library list')
        self.compact_button.toggled.connect(self.toggle_compact_library)
        bar.addWidget(self.compact_button)
        self.compact_button.setVisible(not self.is_grid)
        for button in (self.order, self.filter_button, self.compact_button, *self.view_buttons.values()):
            button.setFixedSize(control_height, control_height)
            icon_size = max(16, round(control_height * .55))
            button.setIconSize(QSize(icon_size, icon_size))
            set_style(button, 'padding: 0;')
        bar.addStretch()
        self.count = label('', 'muted')
        bar.addWidget(self.count)
        toolbar_scroll = HorizontalValuesScroll()
        toolbar_scroll.setWidget(toolbar)
        toolbar_scroll.setWidgetResizable(True)
        toolbar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        toolbar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        toolbar_scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        toolbar_scroll.setFixedHeight(toolbar.sizeHint().height())
        set_style(toolbar_scroll, 'QScrollArea { border: 0; background: #171819; }')
        outer.addWidget(toolbar_scroll)
        self.filter_panel = RevealPanel()
        filters_layout = QGridLayout(self.filter_panel.content)
        filters_layout.setContentsMargins(18, 8, 18, 12)
        self.filter_controls = {}
        for index, (key, title) in enumerate(FILTER_FIELDS):
            combo = QComboBox()
            combo.addItem(f'All {title.lower()}s', '')
            for value in sorted({value for game in self.games for value in values(game, key)}, key=str.casefold):
                combo.addItem(value, value)
            combo.setCurrentIndex(max(0, combo.findData(self.active_filters.get(key, ''))))
            combo.currentIndexChanged.connect(self.refresh_library)
            self.filter_controls[key] = combo
            filters_layout.addWidget(combo, index // 4, index % 4)
        self.installed_filter = QComboBox()
        for title, value in [('All installation states', ''), ('Installed', 'Installed'), ('Not installed', 'Not installed')]:
            self.installed_filter.addItem(title, value)
        self.installed_filter.setCurrentIndex(max(0, self.installed_filter.findData(self.active_filters.get('Installed', ''))))
        self.installed_filter.currentIndexChanged.connect(self.refresh_library)
        filters_layout.addWidget(self.installed_filter, 2, 2)
        self.favorites_filter = QCheckBox('Favorites only')
        self.favorites_filter.setChecked(bool(self.active_filters.get('Favorite')))
        self.favorites_filter.toggled.connect(self.refresh_library)
        filters_layout.addWidget(self.favorites_filter, 2, 0)
        self.hidden_filter = QCheckBox('Show hidden games')
        self.hidden_filter.setChecked(bool(self.active_filters.get('ShowHidden')))
        self.hidden_filter.toggled.connect(self.refresh_library)
        filters_layout.addWidget(self.hidden_filter, 2, 1)
        reset = QPushButton('Clear filters')
        reset.clicked.connect(self.reset_filters)
        filters_layout.addWidget(reset, 2, 3)
        self.filter_panel.setVisible(False)
        self.filters_expanded = False
        self.filter_animation = QVariantAnimation(self)
        self.filter_animation.setDuration(240)
        self.filter_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.filter_animation.valueChanged.connect(lambda value: self.filter_panel.setFixedHeight(round(value)))
        self.filter_animation.finished.connect(self.finish_filter_animation)
        self.filter_button.clicked.connect(lambda: self.set_filters_expanded(not self.filters_expanded))
        outer.addWidget(self.filter_panel)
        split = QSplitter()
        set_style(split, 'QSplitter { background: transparent; }')
        self.split = split
        self.list = LibraryList()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.library_scrollbar_opacity = QGraphicsOpacityEffect(self.list.verticalScrollBar())
        self.library_scrollbar_opacity.setOpacity(1)
        self.list.verticalScrollBar().setGraphicsEffect(self.library_scrollbar_opacity)
        for animation in (self.library_animation, self.filter_animation, self.list.gutter_animation):
            animation.valueChanged.connect(self.update_library_scrollbar_policy)
            animation.stateChanged.connect(self.update_library_scrollbar_policy)
        self.list.setMinimumWidth(160)
        self.list.setIconSize(QSize(48, 48))
        self.list.currentItemChanged.connect(self.select_game)
        self.list.itemSelectionChanged.connect(self.update_compact_library)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.show_game_context_menu)
        split.addWidget(self.list)
        scroll = QScrollArea()
        self.game_scroll = scroll
        self.game_background = ArtworkPage()
        background_layout = QVBoxLayout(self.game_background)
        background_layout.setContentsMargins(0, 0, 0, 0)
        background_layout.addWidget(split)
        set_style(scroll, 'QScrollArea, QScrollArea > QWidget { background: transparent; border: 0; }')
        scroll.viewport().setAutoFillBackground(False)
        scroll.setMinimumWidth(400)
        scroll.setWidgetResizable(True)
        # Reserve the scrollbar's 24px gutter consistently as the page's right
        # padding. Toggling gutter compensation can oscillate at overflow limits.
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        bar = scroll.verticalScrollBar()
        def update_page_scrollbar(minimum, maximum):
            overflow = maximum > minimum
            bar.setEnabled(overflow)
            set_style(bar, '' if overflow and self.filter_animation.state() != QAbstractAnimation.State.Running else 'QScrollBar::handle:vertical { background: transparent; }')
        bar.rangeChanged.connect(update_page_scrollbar)
        update_page_scrollbar(bar.minimum(), bar.maximum())
        self.page = QWidget()
        self.page.setObjectName('page')
        center = QHBoxLayout(self.page)
        center.setContentsMargins(24, 24, 0, 24)
        center.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.content = ResponsiveContent()
        self.content.setObjectName('content')
        self.content.setMinimumWidth(0)
        self.content.setMaximumWidth(1280)
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.details = QVBoxLayout(self.content)
        self.details.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.details.setContentsMargins(0, 0, 0, 0)
        self.details.setSpacing(28)
        self.details.setAlignment(Qt.AlignmentFlag.AlignTop)
        center.addStretch()
        center.addWidget(self.content, 1)
        center.addStretch()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.page)
        split.addWidget(scroll)
        split.setCollapsible(1, False)
        split.setSizes([410, 1130])
        outer.addWidget(self.game_background, 1)
        self.setCentralWidget(root)
        self.apply_panel_appearance()
        self.split.splitterMoved.connect(self.remember_library_width)
        self.configure_view()
        self.filter_games('')
        from .game_detection import GameDetection
        self.game_detection = GameDetection(self.game_providers, lambda: self.games, self,
                                            recorder=self.record_game_session)
        self.game_detection.changed.connect(self.game_status_changed)
        self.game_detection.start()

    def asset(self, game, key):
        repaired = repair_artwork(game, self.data)
        return str(self.data / repaired[key]) if repaired.get(key) else ''

    def thumbnail(self, filename):
        placeholder = themed_asset(Path(__file__).parent / 'assets' /
                                   ('cover-placeholder.svg' if self.is_grid else 'game-placeholder.svg'))
        if not filename:
            filename = placeholder
        size = QSize(160, 240) if self.is_grid else QSize(48, 48)
        ratio = self.devicePixelRatioF()
        try:
            modified = Path(filename).stat().st_mtime_ns
        except OSError:
            return self.thumbnail(placeholder)
        key = (filename, modified, size.width(), size.height(), ratio)
        if key not in self.thumbnail_cache:
            reader = QImageReader(filename)
            reader.setAutoTransform(True)
            target = QSize(round(size.width() * ratio), round(size.height() * ratio))
            original = reader.size()
            if original.isValid():
                reader.setScaledSize(original.scaled(target, Qt.AspectRatioMode.KeepAspectRatio))
            pixmap = QPixmap.fromImage(reader.read())
            if pixmap.isNull() and filename != placeholder:
                return self.thumbnail(placeholder)
            pixmap.setDevicePixelRatio(ratio)
            if len(self.thumbnail_cache) >= 512:
                self.thumbnail_cache.clear()
            icon = QIcon()
            for mode in (QIcon.Mode.Normal, QIcon.Mode.Active, QIcon.Mode.Selected):
                for state in (QIcon.State.Off, QIcon.State.On):
                    icon.addPixmap(pixmap, mode, state)
            self.thumbnail_cache[key] = icon
        return self.thumbnail_cache[key]

    def empty_library_height(self):
        screen = self.screen()
        return min(1140, screen.availableGeometry().height() - 40) if screen else 1140

    def filter_games(self, query):
        self.setMinimumHeight(self.empty_library_height() if not self.games else 0)
        previous = self.current.get('Id') if self.current else self.last_selected
        selection = {item.data(Qt.ItemDataRole.UserRole)['Id'] for item in self.list.selectedItems()}
        self.list.blockSignals(True)
        self.list.clear()
        selected = None
        self.active_filters = {key: control.currentData() for key, control in self.filter_controls.items()}
        self.active_filters.update(Installed=self.installed_filter.currentData(),
                                   Favorite=self.favorites_filter.isChecked(), ShowHidden=self.hidden_filter.isChecked())
        games = query_games(self.games, query, self.active_filters, self.sort.currentData(), self.order.isChecked())
        for game in games:
            artwork = self.asset(game, 'CoverImage' if self.is_grid else 'Icon')
            item = QListWidgetItem(self.thumbnail(artwork), game['Name'])
            item.setToolTip('')
            item.setData(Qt.ItemDataRole.UserRole, game)
            item.setSizeHint(QSize(180, 285) if self.is_grid else QSize(250, 66))
            self.list.addItem(item)
            if game['Id'] == previous:
                selected = item
        self.list.balance_grid()
        self.count.setText(f'{self.list.count()} / {len(self.games)} games')
        active = sum(bool(value) for value in self.active_filters.values())
        self.filter_button.setToolTip(f'Filters ({active} active)' if active else 'Filters')
        self.filter_button.setProperty('activeFilter', bool(active))
        self.filter_button.style().unpolish(self.filter_button)
        self.filter_button.style().polish(self.filter_button)
        if self.list.count():
            self.list.setCurrentItem(selected or self.list.item(0), QItemSelectionModel.SelectionFlag.NoUpdate)
            for index in range(self.list.count()):
                candidate = self.list.item(index)
                candidate.setSelected(candidate.data(Qt.ItemDataRole.UserRole)['Id'] in selection)
            if not self.list.selectedItems():
                self.list.currentItem().setSelected(True)
        self.list.blockSignals(False)
        self.update_compact_library()
        self.select_game(self.list.currentItem())

    def refresh_library(self, *args):
        self.order.setIcon(toolbar_icon('descending' if self.order.isChecked() else 'ascending'))
        self.order.setToolTip('Descending' if self.order.isChecked() else 'Ascending')
        self.settings.setValue('library/sort', self.sort.currentData())
        self.settings.setValue('library/descending', self.order.isChecked())
        self.filter_games(self.search.text())
        self.settings.setValue('library/filters', json.dumps(self.active_filters))
        self.settings.sync()

    def set_filters_expanded(self, expanded):
        self.filters_expanded = expanded
        start = self.filter_panel.height() if self.filter_panel.isVisible() else 0
        self.filter_animation.stop()
        self.game_background.defer_background_render = True
        self.filter_panel.setFixedHeight(start)
        self.filter_panel.show()
        self.library_scrollbar_opacity.setOpacity(0)
        set_style(self.game_scroll.verticalScrollBar(), 'QScrollBar::handle:vertical { background: transparent; }')
        self.filter_animation.blockSignals(True)
        self.filter_animation.setStartValue(float(start))
        self.filter_animation.setEndValue(float(self.filter_panel.sizeHint().height() if expanded else 0))
        self.filter_animation.blockSignals(False)
        self.filter_animation.start()

    def finish_filter_animation(self):
        self.filter_panel.setVisible(self.filters_expanded)
        if self.filters_expanded:
            self.filter_panel.setFixedHeight(self.filter_panel.sizeHint().height())
        self.game_background.defer_background_render = False
        self.game_background.update()
        self.update_library_scrollbar_policy()
        bar = self.game_scroll.verticalScrollBar()
        set_style(bar, '' if bar.maximum() > bar.minimum() else 'QScrollBar::handle:vertical { background: transparent; }')

    def apply_metadata_filter(self, key, value):
        control = self.filter_controls[key]
        index = control.findData(value)
        if index < 0:
            control.addItem(str(value), value)
            index = control.count() - 1
        self.search.clear()
        control.setCurrentIndex(index)
        self.set_filters_expanded(True)

    def reset_filters(self):
        controls = list(self.filter_controls.values()) + [self.installed_filter, self.favorites_filter, self.hidden_filter]
        for control in controls:
            control.blockSignals(True)
            if isinstance(control, QComboBox):
                control.setCurrentIndex(0)
            else:
                control.setChecked(False)
            control.blockSignals(False)
        self.search.clear()
        self.refresh_library()

    def remember_library_width(self, *_):
        if self.compact_library or self.list.width_transition or self.list.gutter_animation.state() == QAbstractAnimation.State.Running:
            return
        key = 'grid' if self.is_grid else 'list'
        width = self.split.sizes()[0]
        self.library_widths[key] = width
        self.settings.setValue(f'library/{key}Width', width)
        self.settings.sync()

    def restore_library_width(self):
        width = self.library_widths['grid' if self.is_grid else 'list']
        total = max(self.split.width(), self.width()) - self.split.handleWidth()
        self.split.setSizes([width, max(1, total - width)])

    def configure_view(self):
        self.list.setViewMode(QListView.ViewMode.IconMode if self.is_grid else QListView.ViewMode.ListMode)
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setUniformItemSizes(True)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.verticalScrollBar().setSingleStep(96 if self.is_grid else 24)
        self.list.setWrapping(self.is_grid)
        self.list.setWordWrap(self.is_grid)
        self.list.setSpacing(0 if self.is_grid else 3)
        self.list.setIconSize(QSize(160, 240) if self.is_grid else QSize(48, 48))
        self.list.setGridSize(QSize(180, 285) if self.is_grid else QSize())
        self.restore_library_width()

    def select_view(self, index):
        self.view.setCurrentIndex(index)
        for key, button in self.view_buttons.items():
            button.setChecked(self.view.currentData() == key)

    def change_view(self, *args):
        self.switching_library_view = True
        self.library_animation.stop()
        self.list.gutter_animation.stop()
        self.list.width_transition = False
        self.list.hide_hover_immediately()
        self.content.cover_animation.stop()
        self.is_grid = self.view.currentData() == 'grid'
        self.compact_button.setVisible(not self.is_grid)
        for key, button in self.view_buttons.items():
            button.setChecked(self.view.currentData() == key)
        self.settings.setValue('library/view', 'grid' if self.is_grid else 'list')
        self.configure_view()
        self.filter_games(self.search.text())
        self.content.layout().activate()
        self.update_library_scrollbar_policy()
        QTimer.singleShot(0, lambda: setattr(self, 'switching_library_view', False))

    def update_filter_choices(self):
        for key, title in FILTER_FIELDS:
            control = self.filter_controls[key]
            selected = control.currentData()
            control.blockSignals(True)
            control.clear()
            control.addItem(f'All {title.lower()}s', '')
            for value in sorted({value for game in self.games for value in values(game, key)}, key=str.casefold):
                control.addItem(value, value)
            control.setCurrentIndex(max(0, control.findData(selected)))
            control.blockSignals(False)

    def select_game(self, item, previous=None):
        selected = item.data(Qt.ItemDataRole.UserRole) if item else None
        selected_id = selected.get('Id') if selected else None
        current_id = self.current.get('Id') if self.current else None
        position = self.game_scroll.verticalScrollBar().value() if selected_id == current_id else 0
        self.game_view_generation = getattr(self, 'game_view_generation', 0) + 1
        generation = self.game_view_generation
        self.game_scroll.setUpdatesEnabled(False)
        self.content.cover_animation.stop()
        try:
            self.build_game_view(item)
        except Exception:
            self.game_scroll.setUpdatesEnabled(True)
            raise
        def finish_switch():
            if generation != self.game_view_generation:
                return
            try:
                # Showing new children and sizing the header posts more layout
                # requests. Resolve these without processing any paint events.
                self.page.ensurePolished()
                for _ in range(3):
                    self.details.invalidate()
                    self.details.activate()
                    self.page.layout().activate()
                    QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
                self.game_scroll.verticalScrollBar().setValue(position)
            finally:
                self.game_scroll.setUpdatesEnabled(True)
        QTimer.singleShot(0, finish_switch)

    def build_game_view(self, item):
        while self.details.count():
            child = self.details.takeAt(0)
            if child.widget():
                child.widget().hide()
                child.widget().deleteLater()
        selected = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.content.cover = None
        self.content.description_links_row = None
        self.content.installation_row = None
        self.current = next((game for game in self.games if game['Id'] == selected['Id']), None) if selected else None
        if not self.current:
            self.game_background.set_background(QPixmap())
            if self.games:
                self.details.addWidget(label('No matching games.', 'muted'))
            return
        game = self.current
        self.game_background.set_background(self.asset(game, 'BackgroundImage'),
                                           self.settings.value('appearance/backgroundBlur', 48, type=int))
        self.last_selected = game['Id']
        self.settings.setValue('lastSelectedGame', self.last_selected)
        if not hasattr(self, 'selection_settings_timer'):
            self.selection_settings_timer = QTimer(self)
            self.selection_settings_timer.setSingleShot(True)
            self.selection_settings_timer.setInterval(250)
            self.selection_settings_timer.timeout.connect(self.settings.sync)
        self.selection_settings_timer.start()
        play = QPushButton('Play')
        self.play_button = play
        play.setObjectName('play')
        play.setEnabled(any(provider.owns(game) for provider in self.game_providers))
        play.clicked.connect(self.play_game)
        hero = Hero(play, self.edit_game, self.delete_game, self.plugin_game_actions(game))
        self.play_hero = hero
        hero.pixmap = QPixmap(self.asset(game, 'HeaderImage' if 'HeaderImage' in game else 'BackgroundImage'))
        if hero.pixmap.isNull():
            hero.setFixedHeight(hero.play_control.sizeHint().height() + 16)
        else:
            hero.setFixedHeight(max(240, round(self.content.width() * hero.pixmap.height() / hero.pixmap.width())))
        self.details.addWidget(hero)
        row = QWidget()
        row.setObjectName('content')
        columns = QHBoxLayout(row)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(24)
        cover = QLabel()
        cover.setObjectName('cover')
        image = QPixmap(self.asset(game, 'CoverImage'))
        has_cover = not image.isNull()
        if has_cover:
            self.content.cover = cover
            ratio = self.devicePixelRatioF()
            scaled_cover = image.scaled(round(190 * ratio), round(295 * ratio),
                                       Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            scaled_cover.setDevicePixelRatio(ratio)
            cover.setPixmap(scaled_cover)
            logical_size = scaled_cover.deviceIndependentSize().toSize()
            cover.setFixedSize(logical_size)
            panel_height = logical_size.height()
        else:
            cover.hide()
            panel_height = 295
        hero.align_with_cover(cover.width() if has_cover else 0)
        row.setFixedHeight(panel_height)
        if has_cover:
            cover.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            columns.addWidget(cover, 0, Qt.AlignmentFlag.AlignTop)
        information, info = card()
        information.setFixedHeight(panel_height)
        info.setSpacing(8)
        description = Description(game.get('Description') or '<p>No description yet.</p>')
        info.addWidget(description, 1)
        release = game.get('ReleaseDate') or ''
        if isinstance(release, dict):
            release = release.get('ReleaseDate', '')
        info.addWidget(label('Details', 'section'))
        form = QFormLayout()
        form.setHorizontalSpacing(22)
        form.setVerticalSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for title, key in [('Developer', 'Developers'), ('Publisher', 'Publishers'), ('Features', 'Features')]:
            values = game.get(key) or []
            if isinstance(values, str):
                values = [values]
            if values:
                form.addRow(label(title, 'muted'), horizontal_values(values, on_click=lambda value, key=key: self.apply_metadata_filter(key, value)))
        info.addLayout(form)
        if release:
            info.addWidget(horizontal_values([release], 'muted', lambda value: self.apply_metadata_filter('ReleaseDate', value)))
        for key in ('Platforms', 'Genres'):
            values = game.get(key) or (['PC (Windows)'] if key == 'Platforms' else [])
            if values:
                info.addWidget(horizontal_values(values, 'muted', lambda value, key=key: self.apply_metadata_filter(key, value), separator=' · '))
        columns.addWidget(information, 1, Qt.AlignmentFlag.AlignTop)
        links_size = QSize(logical_size) if has_cover else QSize(190, panel_height)
        self.content.update_cover()
        self.details.addWidget(row)
        description_row = DescriptionLinksRow()
        description_columns = description_row.columns
        full_description = game.get('FullDescription', '')
        if self.settings.value('descriptions/hideRepeatedSentences', False, type=bool):
            from .description_overlap import hide_repeated_sentences
            full_description = hide_repeated_sentences(game.get('Description', ''), full_description)
        if full_description:
            from .rich_description import CollapsibleDescription
            full_card, full_layout = card()
            full_layout.addWidget(label('Description', 'section'))
            description_panel = CollapsibleDescription(full_description)
            full_layout.addWidget(description_panel)
            description_row.description = full_card
            full_card.installEventFilter(description_row)
            description_columns.addWidget(full_card, 1, Qt.AlignmentFlag.AlignTop)
        else:
            description_columns.addStretch(1)
        if game.get('Links'):
            links, link_layout = card()
            links.setProperty('linksPanel', True)
            links.setFixedSize(links_size)
            description_row.links = links
            description_row.links_size = links_size
            link_layout.addWidget(label('Links', 'section'))
            flow = LinkLayout()
            flow.setSpacing(22)
            flow.row_spacing = 6
            link_content = LinkContent()
            set_style(link_content, 'background: transparent;')
            link_content.setLayout(flow)
            names = load_names(self.settings)
            for link in game['Links']:
                name = friendly_name(link['Url'], link.get('Name') or link['Url'], names, game.get('Name', ''))
                button = QLabel(f'<a href="{html.escape(link["Url"], quote=True)}" '
                                f'style="color: {colour("text")}; text-decoration: none;">{html.escape(name)}</a>')
                button.setObjectName('link')
                button.setWordWrap(True)
                button.setToolTip(link['Url'])
                button.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse | Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
                set_style(button, 'QLabel { background: transparent; padding: 2px 0; }')
                button.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
                flow.addWidget(button)
            link_scroll = LinksScroll(link_content, flow)
            description_row.link_scroll = link_scroll
            link_scroll.fit_rows()
            link_layout.addWidget(link_scroll)
            description_columns.addWidget(links, 0, Qt.AlignmentFlag.AlignTop)
        if game.get('FullDescription') or game.get('Links'):
            self.details.addWidget(description_row)
            self.content.description_links_row = description_row
            self.content.update_cover()
        else:
            description_row.deleteLater()
        def display_date(value, fallback):
            if not value:
                return fallback
            try:
                date = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
                return date.strftime('%Y-%m-%d %H:%M' if 'T' in str(value) or ' ' in str(value) else '%Y-%m-%d')
            except ValueError:
                return str(value)

        installation_row = DescriptionLinksRow()
        installation_row.setObjectName('installationRow')
        installation, folder_layout = card()
        installation.setProperty('installationPanel', True)
        heading = QHBoxLayout()
        heading.addWidget(label('Installation', 'section'))
        if game.get('ArchivePath'):
            badge = QLabel('Archived')
            badge.setObjectName('archiveIndicator')
            badge.setToolTip(game['ArchivePath'])
            archive_icon = QLabel()
            archive_icon.setPixmap(QIcon(str(Path(__file__).parent / 'assets/archive.svg')).pixmap(20, 20))
            heading.addWidget(archive_icon)
            heading.addWidget(badge)
        heading.addStretch()
        folder_layout.addLayout(heading)
        installation_form = QFormLayout()
        installation_form.setHorizontalSpacing(22)
        installation_form.setVerticalSpacing(8)
        installation_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        installation_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        if game.get('ArchivePath'):
            archived = QPushButton(game['ArchivePath'])
            archived.setToolTip(game['ArchivePath'])
            archived.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(game['ArchivePath'])))
            installation_form.addRow(label('Archive', 'muted'), archived)
        if game.get('InstallDirectory'):
            folder = QPushButton(game['InstallDirectory'])
            folder.setObjectName('folder')
            folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(game['InstallDirectory'])))
            set_style(folder, 'QPushButton#folder { padding: 0; }')
            folder.setFixedSize(folder.sizeHint().width(), folder.fontMetrics().height())
            folder.setToolTip(game['InstallDirectory'])
            folder_scroll = HorizontalValuesScroll()
            set_style(folder_scroll, 'QScrollArea, QScrollArea > QWidget { background: transparent; border: 0; }')
            folder_scroll.setFrameShape(QFrame.Shape.NoFrame)
            folder_scroll.viewport().setAutoFillBackground(False)
            folder_scroll.setWidget(folder)
            folder_scroll.setWidgetResizable(False)
            folder_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            folder_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            folder_scroll.setFixedHeight(folder.height())
            folder_scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            folder_scroll.fades = ScrollFades(folder_scroll, horizontal=True)
            installation_form.addRow(label('Folder', 'muted'), folder_scroll)
            self.installation_size_label = label('Calculating size…')
            installation_form.addRow(label('Size', 'muted'), self.installation_size_label)
            self.show_installation_size(game)
        else:
            installation_form.addRow(label('Folder', 'muted'), label('Not installed'))
            installation_form.addRow(label('Size', 'muted'), label('Unavailable'))
        installation_form.addRow(label('Added date', 'muted'), label(display_date(game.get('Added'), 'Unknown')))
        folder_layout.addLayout(installation_form)
        history, history_layout = card()
        history.setProperty('playHistoryPanel', True)
        history_layout.addWidget(label('Play history', 'section'))
        seconds = max(0, int(game.get('Playtime') or 0))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration = f'{hours}h {minutes}m' if hours else f'{minutes}m' if minutes else f'{seconds}s'
        history_form = QFormLayout()
        history_form.setHorizontalSpacing(22)
        history_form.setVerticalSpacing(8)
        history_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        history_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.history_labels = {}
        for title, value in [('Play time', duration),
                             ('Last played', display_date(game.get('LastActivity'), 'Never')),
                             ('Play count', str(game.get('PlayCount') or 0))]:
            self.history_labels[title] = label(value)
            history_form.addRow(label(title, 'muted'), self.history_labels[title])
        history_layout.addLayout(history_form)
        installation_row.columns.addWidget(history, 1, Qt.AlignmentFlag.AlignTop)
        installation_row.columns.addWidget(installation, 1, Qt.AlignmentFlag.AlignTop)
        self.details.addWidget(installation_row)
        self.content.installation_row = installation_row
        self.content.update_cover()
        self.apply_panel_appearance()
        if hasattr(self, 'game_detection'):
            self.game_status_changed(game['Id'], self.game_detection.status(game['Id']))

    def record_game_session(self, game_id, seconds, count, stamp):
        from .game_detection import record_playtime
        try:
            self.games = record_playtime(self.data, self.games, game_id, seconds, count, stamp)
        except (OSError, ValueError):
            import logging
            logging.exception('Could not save play history for %s', game_id)
            return False
        updated = next((game for game in self.games if game['Id'] == game_id), None)
        if updated is None:
            return
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item.data(Qt.ItemDataRole.UserRole)['Id'] == game_id:
                item.setData(Qt.ItemDataRole.UserRole, updated)
        if self.current and self.current['Id'] == game_id:
            self.current.update(updated)
            total = int(updated.get('Playtime') or 0)
            hours, remainder = divmod(total, 3600)
            minutes, seconds = divmod(remainder, 60)
            duration = f'{hours}h {minutes}m' if hours else f'{minutes}m' if minutes else f'{seconds}s'
            self.history_labels['Play time'].setText(duration)
            self.history_labels['Play count'].setText(str(updated['PlayCount']))
            self.history_labels['Last played'].setText(datetime.fromisoformat(stamp).strftime('%Y-%m-%d %H:%M'))

    def game_status_changed(self, game_id, status):
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item.data(Qt.ItemDataRole.UserRole)['Id'] == game_id:
                item.setToolTip(status if status in ('Running', 'Launching', 'Launch failed') else '')
        if self.current and self.current['Id'] == game_id:
            active = status in ('Running', 'Launching')
            self.play_button.setText(status + ('…' if status == 'Launching' else '') if active else 'Play')
            self.play_button.setEnabled(not active and any(provider.owns(self.current) for provider in self.game_providers))
            self.play_hero.position_play_control()

    def apply_panel_appearance(self):
        self.list.panel_transparency = max(0, min(100, self.settings.value('appearance/sidePanelTransparency', 0, type=int)))
        self.list.viewport().setAutoFillBackground(False)
        self.list.update_scrollbar_padding()
        transparency = max(0, min(100, self.settings.value('appearance/gamePanelTransparency', 0, type=int)))
        alpha = round(255 * (1 - transparency / 100))
        for panel in self.content.findChildren(QFrame):
            if panel.objectName() == 'card':
                set_style(panel, f'QFrame#card {{ background: rgba(29, 30, 32, {alpha}); border-radius: 16px; }}')

    def show_installation_size(self, game):
        directory = game['InstallDirectory']
        size = game.get('InstallSize')
        if size is None:
            size = self.installation_sizes.get(directory)
        def display(value):
            amount = float(value)
            for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
                if amount < 1000 or unit == 'TB':
                    return f'{amount:.2f} {unit}' if unit != 'B' else f'{int(amount)} B'
                amount /= 1000
        if isinstance(size, (int, float)) and size > 0:
            self.installation_size_label.setText(display(size))
            return
        if not Path(directory).is_dir():
            self.installation_size_label.setText('Size unavailable')
            return
        from .metadata_dialog import Task
        from .installation import installation_size
        task = Task(lambda: installation_size(directory))
        self.size_tasks.append(task)
        def complete(value):
            self.installation_sizes[directory] = value
            # A size scan can finish after an archive or play-history update.
            from .library_storage import library_lock
            from .storage import atomic_json
            with library_lock(self.data):
                path = self.data / 'library.json'
                if path.exists():
                    self.games = json.loads(path.read_text())
            latest = next((entry for entry in self.games if entry['Id'] == game['Id'] and entry.get('InstallDirectory') == directory), None)
            if latest is not None:
                try:
                    with library_lock(self.data):
                        self.games = json.loads(path.read_text()) if path.exists() else self.games
                        saved = next((entry for entry in self.games if entry['Id'] == game['Id']
                                      and entry.get('InstallDirectory') == directory), None)
                        if saved is not None:
                            saved['InstallSize'] = value
                            atomic_json(path, self.games)
                    if self.current and self.current['Id'] == game['Id']:
                        self.current = next((entry for entry in self.games if entry['Id'] == game['Id']), None)
                except OSError:
                    latest['InstallSize'] = value
            for editor in self.findChildren(MetadataEditor):
                if editor.isVisible() and editor.game['Id'] == game['Id'] and not editor.fields['InstallSize'].text().strip():
                    editor.fields['InstallSize'].setText(str(value))
            if self.current and self.current['Id'] == game['Id']:
                self.installation_size_label.setText(display(value))
            self.size_tasks.remove(task)
        def failed(error):
            if self.current and self.current['Id'] == game['Id']:
                self.installation_size_label.setText('Size unavailable')
            self.size_tasks.remove(task)
        task.signals.succeeded.connect(complete)
        task.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(task)

    def play_game(self):
        if self.current is None:
            return
        if self.game_detection.status(self.current['Id']) in ('Launching', 'Running'):
            return
        try:
            game = dict(self.current)
            from .play_actions import actions_for
            actions = actions_for(game, self.game_providers)
            if not actions:
                raise ValueError('Add a play action on the Installation page.')
            action = actions[0]
            if len(actions) > 1:
                from .add_game import AddGameMethods
                choices = [(item['Name'], item) for item in actions]
                picker = AddGameMethods(choices, self)
                picker.setWindowTitle('Choose play action')
                picker.findChild(QLabel).setText('Choose how to launch this game.')
                if run_dialog(picker) != QDialog.DialogCode.Accepted:
                    return
                action = picker.selected_method
            provider = next((provider for provider in self.game_providers
                             if provider.id == action['Integration']), None)
            if provider is None:
                raise ValueError(f'The integration for “{action["Name"]}” is unavailable.')
            for plugin in self.generic_plugins:
                if not plugin.before_launch(self, game):
                    return
            game = next(entry for entry in self.games if entry['Id'] == game['Id'])
            from .providers import IntegrationPlugin
            if isinstance(provider, IntegrationPlugin):
                self.game_detection.launching(game['Id'])
            provider.launch_action(game, action)
        except Exception as error:
            self.game_detection.launch_failed(game['Id'])
            show_warning(self, 'Cannot launch game', str(error))

    def plugin_game_actions(self, game):
        return [(plugin.name, actions) for plugin in self.generic_plugins
                if (actions := plugin.game_actions(self, game))]

    def import_provider_games(self, provider):
        try:
            imported = provider.import_games()
            # Preserve metadata and artwork for games already associated with a provider.
            known = {provider.association_id(game) for game in self.games if provider.owns(game)}
            added = [game for game in imported if provider.association_id(game) not in known]
            dialog = QDialog(self)
            dialog.setWindowTitle(f'Add game from {provider.name}')
            dialog.resize(480, 520)
            layout = QVBoxLayout(dialog)
            search = QLineEdit()
            search.setPlaceholderText('Search games')
            layout.addWidget(search)
            games_list = QListWidget()
            layout.addWidget(games_list)
            for game in sorted(added, key=lambda game: game['Name'].casefold()):
                item = QListWidgetItem(game['Name'])
                item.setData(Qt.ItemDataRole.UserRole, game)
                games_list.addItem(item)
            def filter_choices(query):
                for index in range(games_list.count()):
                    item = games_list.item(index)
                    item.setHidden(query.casefold() not in item.text().casefold())
                current = games_list.currentItem()
                add.setEnabled(current is not None and not current.isHidden())
            search.textChanged.connect(filter_choices)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
            add = buttons.addButton('Add selected game', QDialogButtonBox.ButtonRole.AcceptRole)
            add.setEnabled(False)
            games_list.currentItemChanged.connect(lambda item, previous: add.setEnabled(item is not None and not item.isHidden()))
            add.clicked.connect(dialog.accept)
            games_list.itemDoubleClicked.connect(lambda item: dialog.accept())
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            if not added:
                layout.insertWidget(0, QLabel('No games available to add. Existing games are already in Playlite.'))
            if (run_dialog(dialog) != QDialog.DialogCode.Accepted
                    or games_list.currentItem() is None or games_list.currentItem().isHidden()):
                return
            added = [games_list.currentItem().data(Qt.ItemDataRole.UserRole)]
            from .storage import atomic_json
            from .library_storage import library_lock
            with library_lock(self.data):
                path = self.data / 'library.json'
                latest = json.loads(path.read_text()) if path.exists() else self.games
                if path.exists():
                    shutil.copy2(path, self.data / 'library.json.bak')
                self.games = latest + added
                atomic_json(path, self.games)
            self.last_selected = added[0]['Id']
            self.search.clear()
            self.update_filter_choices()
            self.refresh_library()
            from .add_game import AddGameEditor
            game = added[0]
            editor = AddGameEditor(game['Executable'], self.data, self, game=game)
            while run_dialog(editor) == QDialog.DialogCode.Accepted:
                try:
                    self.games = save_game(self.data, self.games, editor.result_game)
                except OSError as error:
                    editor.error.setText(f'Could not save the Playlite entry: {error}')
                    continue
                self.update_filter_choices()
                self.refresh_library()
                for plugin in editor.generic_plugins:
                    plugin.after_game_added(self, editor.result_game, editor)
                break
            for cache in editor.download_caches:
                cache.cleanup()
        except Exception as error:
            show_warning(self, 'Cannot import games', str(error))

    def toggle_compact_library(self, checked):
        self.prefer_compact_library = checked
        self.settings.setValue('library/compact', checked)
        if self.is_grid and checked:
            self.select_view(0)
        self.update_compact_library()

    def animate_library_width(self, value):
        width = round(value)
        self.list.setFixedWidth(width)
        total = self.split.width() - self.split.handleWidth()
        self.split.setSizes([width, max(1, total - width)])

    def update_library_scrollbar_policy(self, *_):
        running = [animation for animation in
                   (self.library_animation, self.filter_animation, self.list.gutter_animation)
                   if animation.state() == QAbstractAnimation.State.Running]
        opacity = min((animation.easingCurve().valueForProgress(
            animation.currentTime() / max(1, animation.duration())) for animation in running), default=1)
        if self.list.width_transition and self.library_animation not in running:
            opacity = 0
        self.library_scrollbar_opacity.setOpacity(opacity)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def finish_library_transition(self):
        self.list.width_transition = False
        if self.compact_library:
            self.list.setFixedWidth(self.list.compact_width())
        else:
            self.list.setMinimumWidth(160)
            self.list.setMaximumWidth(16777215)
            self.restore_library_width()
        self.update_library_scrollbar_policy()

    def update_compact_library(self):
        if not hasattr(self, 'list'):
            return
        compact = (self.width() < 900 or self.prefer_compact_library) and not self.is_grid
        changed = compact != self.compact_library
        start_width = self.list.width()
        animate = changed and self.isVisible() and self.toolbar_launch_settled and not getattr(self, 'switching_library_view', False)
        if changed:
            self.library_animation.stop()
            self.list.gutter_animation.stop()
            self.list.width_transition = animate
            self.update_library_scrollbar_policy()
        self.compact_library = compact
        self.list.compact_enabled = compact
        self.list.update_scrollbar_padding()
        if changed:
            self.list.hide_hover_immediately()
        if animate:
            target = self.list.compact_width() if compact else self.library_widths['grid' if self.is_grid else 'list']
            self.library_animation.blockSignals(True)
            self.library_animation.setStartValue(float(start_width))
            self.library_animation.setEndValue(float(target))
            self.library_animation.blockSignals(False)
            self.library_animation.start()
        elif not self.list.width_transition:
            if compact:
                self.list.fit_compact_width()
            else:
                self.list.setMinimumWidth(160)
                self.list.setMaximumWidth(16777215)
                if changed:
                    self.restore_library_width()
        if not self.is_grid:
            for index in range(self.list.count()):
                item = self.list.item(index)
                game = item.data(Qt.ItemDataRole.UserRole)
                item.setText('' if compact else game['Name'])
                item.setSizeHint(QSize(64 if compact else 0, 66))
        self.list.update_selected_rows()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'list'):
            QTimer.singleShot(0, self.update_compact_library)
        if self.isVisible() and not (self.isMaximized() or self.isFullScreen() or self.isMinimized()):
            self.last_normal_size = QSize(event.size())

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            old_state = event.oldState()
            if (self.isMaximized() or self.isFullScreen()) and not (old_state & (Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen)):
                normal = self.normalGeometry().size()
                if normal.isValid():
                    self.last_normal_size = QSize(normal)

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'game_detection'):
            self.game_detection.start()
        if self.fit_default_height:
            self.fit_default_height = False
            QTimer.singleShot(0, self.fit_content_height)

    def fit_content_height(self, settle=True):
        self.page.layout().activate()
        for links in self.content.findChildren(LinksScroll):
            links.fit_rows()
        self.details.activate()
        width = self.content.width()
        height = self.details.totalHeightForWidth(width)
        if height < 0:
            height = self.details.minimumSize().height()
        margins = self.page.layout().contentsMargins()
        overhead = self.height() - self.game_scroll.viewport().height()
        required = height + margins.top() + margins.bottom() + overhead
        if not self.games:
            required = self.empty_library_height()
        screen = self.screen()
        if screen:
            decoration = max(0, self.frameGeometry().height() - self.height())
            required = min(required, screen.availableGeometry().height() - decoration)
        self.resize(self.width(), required)
        if settle:
            QTimer.singleShot(0, lambda: self.fit_content_height(False))
        else:
            self.toolbar_launch_settled = True

    def save_window_state(self):
        for key in ('window/geometry', 'window/normalSize', 'window/normalSizeThirdWidth',
                    'window/normalSizeHalfWidth', 'window/normalSizeFit', 'window/normalSizeStable'):
            self.settings.remove(key)
        self.settings.sync()

    def closeEvent(self, event):
        if hasattr(self, 'selection_settings_timer'):
            self.selection_settings_timer.stop()
        self.game_detection.stop()
        self.save_window_state()
        super().closeEvent(event)

    def open_settings(self):
        from .settings import SettingsDialog
        active = next((dialog for dialog in self.findChildren(SettingsDialog) if dialog.isVisible()), None)
        if active:
            active.raise_()
            active.activateWindow()
            return
        if run_dialog(SettingsDialog(self.settings, self)) == QDialog.DialogCode.Accepted:
            self.order.setIcon(toolbar_icon('descending' if self.order.isChecked() else 'ascending'))
            self.filter_button.setIcon(toolbar_icon('filters'))
            self.compact_button.setIcon(toolbar_icon('compact'))
            for kind, button in self.view_buttons.items():
                button.setIcon(toolbar_icon(kind))
            self.thumbnail_cache.clear()
            for index in range(self.list.count()):
                item = self.list.item(index)
                game = item.data(Qt.ItemDataRole.UserRole)
                item.setIcon(self.thumbnail(self.asset(game, 'CoverImage' if self.is_grid else 'Icon')))
            self.apply_panel_appearance()
            if self.current:
                position = self.game_scroll.verticalScrollBar().value()
                self.select_game(self.list.currentItem())
                self.game_scroll.verticalScrollBar().setValue(position)

    def add_game(self):
        self.add_manual_game()

    def add_manual_game(self, installation_method=None):
        active = next((dialog for dialog in self.findChildren(QDialog) if dialog.isVisible()), None)
        if active:
            active.raise_()
            active.activateWindow()
            return
        from .add_game import AddGameEditor
        try:
            dialog = AddGameEditor(None, self.data, self, installation_method=installation_method)
        except (ValueError, OSError) as error:
            show_warning(self, 'Cannot add game', str(error))
            return
        while run_dialog(dialog) == QDialog.DialogCode.Accepted:
            try:
                self.games = save_game(self.data, self.games, dialog.result_game)
            except OSError as error:
                dialog.error.setText(f'Could not save the Playlite entry: {error}')
                continue
            self.last_selected = dialog.result_game['Id']
            self.search.clear()
            self.update_filter_choices()
            self.refresh_library()
            for cache in dialog.download_caches:
                cache.cleanup()
            for plugin in dialog.generic_plugins:
                plugin.after_game_added(self, dialog.result_game, dialog)
            break

    def selected_games(self):
        identities = {item.data(Qt.ItemDataRole.UserRole)['Id'] for item in self.list.selectedItems()}
        return [dict(game) for game in self.games if game['Id'] in identities]

    def show_game_context_menu(self, position):
        item = self.list.itemAt(position)
        if item is None:
            return
        if not item.isSelected():
            self.list.clearSelection()
            item.setSelected(True)
        self.list.setCurrentItem(item, QItemSelectionModel.SelectionFlag.NoUpdate)
        self.list.hide_hover_immediately(preserve_selected=True)
        games = self.selected_games()
        actions = self.plugin_game_actions(games[0]) if len(games) == 1 else [
            (plugin.name, actions) for plugin in self.generic_plugins
            if (actions := plugin.batch_game_actions(self, games))]
        menu = game_context_menu(self.list, self.edit_game if len(games) == 1 else None,
                                 lambda: self.delete_games(games), actions)
        menu.aboutToHide.connect(menu.deleteLater)
        menu.popup(self.list.viewport().mapToGlobal(position))

    def delete_game(self):
        if self.current is not None:
            self.delete_games([dict(self.current)])

    def delete_games(self, games):
        if not games:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Delete game' if len(games) == 1 else 'Delete games')
        layout = QVBoxLayout(dialog)
        message = QLabel(f'Remove “{games[0]["Name"]}” from Playlite?' if len(games) == 1
                         else f'Remove {len(games)} selected games from Playlite?')
        message.setWordWrap(True)
        layout.addWidget(message)
        providers = {game['Id']: next((provider for provider in self.game_providers
                     if getattr(provider, 'supports_entry_deletion', False) and provider.owns(game)), None)
                     for game in games}
        remove_launcher = QCheckBox('Also delete associated launcher entries')
        remove_launcher.setEnabled(any(providers.values()))
        layout.addWidget(remove_launcher)
        layout.addWidget(QLabel('Game files, archives, and Wine prefixes will be kept.'))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        delete = buttons.addButton('Delete', QDialogButtonBox.ButtonRole.AcceptRole)
        delete.clicked.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if run_dialog(dialog) != QDialog.DialogCode.Accepted:
            return
        from .storage import atomic_json
        backups = []
        try:
            from .library_storage import library_lock
            with library_lock(self.data):
                latest = json.loads((self.data / 'library.json').read_text())
                identities = {game['Id'] for game in games}
                remaining = [entry for entry in latest if entry['Id'] not in identities]
                shutil.copy2(self.data / 'library.json', self.data / 'library.json.bak')
                if remove_launcher.isChecked():
                    for game in games:
                        provider = providers[game['Id']]
                        if provider is not None:
                            backups.append((provider, provider.delete_entry(game)))
                atomic_json(self.data / 'library.json', remaining)
        except Exception as error:
            for provider, backup in reversed(backups):
                provider.restore_deleted_entry(backup)
            show_warning(self, 'Could not delete games', str(error))
            return
        self.games = remaining
        self.update_filter_choices()
        self.refresh_library()

    def edit_game(self):
        active = next((dialog for dialog in self.findChildren(QDialog) if dialog.isVisible()), None)
        if active:
            active.raise_()
            active.activateWindow()
            return
        dialog = MetadataEditor(self.current, self.data, self)
        while run_dialog(dialog) == QDialog.DialogCode.Accepted:
            try:
                self.games = save_game(self.data, self.games, dialog.result_game)
            except (OSError, ValueError) as error:
                dialog.error.setText(f'Could not save game: {error}')
                continue
            self.update_filter_choices()
            self.refresh_library()
            for cache in dialog.download_caches:
                cache.cleanup()
            break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=DATA)
    parser.add_argument('--screenshot', type=Path, help='Render an offscreen preview and exit.')
    args = parser.parse_args()
    app = QApplication(['playlite'])
    app.setApplicationName('playlite')
    app.setApplicationDisplayName('Playlite')
    app.setDesktopFileName('playlite')
    app.setWindowIcon(QIcon(str(Path(__file__).parent / 'assets' / 'playlite.png')))
    set_style(app, STYLE)
    from .lifecycle import SingleInstance, TrayLifecycle
    instance = None
    if not args.screenshot:
        instance = SingleInstance(app)
        lifecycle = None
        if not instance.start(lambda: lifecycle.restore() if lifecycle else None):
            return
        app.aboutToQuit.connect(instance.stop)
    if not args.screenshot:
        from .plugin_catalogue_cache import catalogue_cache
        QTimer.singleShot(0, catalogue_cache().refresh)
    window = LibraryWindow(args.data)
    app.aboutToQuit.connect(window.save_window_state)
    app.aboutToQuit.connect(window.game_detection.stop)
    if not args.screenshot:
        lifecycle = TrayLifecycle(window, app)
        window.lifecycle = lifecycle
    window.show()
    if args.screenshot:
        for _ in range(5):
            app.processEvents()
        window.grab().save(str(args.screenshot))
    else:
        sys.exit(app.exec())
