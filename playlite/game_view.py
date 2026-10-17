"""Detail-pane rendering and responsive widgets, independent of library storage."""
import html
from pathlib import Path
from PyQt6.QtCore import Qt, QSize, QRect, QRectF, QEvent, QVariantAnimation, QEasingCurve, QThreadPool
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QColor, QPainterPath
from PyQt6.QtWidgets import (QWidget, QMenu, QPushButton, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QScrollArea, QSizePolicy, QTextBrowser, QLayout, QBoxLayout,
    QStyleOptionButton, QStyle)
from .theme import colour, set_style, themed_asset
from .scroll_fades import ScrollFades, HorizontalValuesScroll


class ArtworkPage(QWidget):
    def __init__(self):
        super().__init__()
        self.background = QPixmap()
        self.previous_backgrounds = []
        self.background_mix = 1.0
        self.background_fade = QVariantAnimation(self)
        self.background_fade.setDuration(240)
        self.background_fade.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.background_fade.valueChanged.connect(self.blend_background)
        self.background_fade.finished.connect(self.finish_background_fade)

    def blend_background(self, value):
        self.background_mix = float(value)
        self.update()

    def finish_background_fade(self):
        self.previous_backgrounds.clear()
        self.background_mix = 1.0
        self.update()

    def transition_background(self, pixmap):
        if pixmap.cacheKey() == self.background.cacheKey():
            return
        # Preserve an interrupted fade exactly, rather than snapping to its target.
        self.background_fade.stop()
        if self.background_mix >= 1:
            self.previous_backgrounds = [(self.background, 1.0)]
        elif self.background_mix > 0:
            self.previous_backgrounds.append((self.background, self.background_mix))
        self.background = pixmap
        self.background_mix = 0.0
        self.background_fade.setStartValue(0.0)
        self.background_fade.setEndValue(1.0)
        self.background_fade.start()

    def set_background(self, source, blur_radius=2, darkness=84, preserve=False):
        # Keep the historical keyword for callers; transitions always preserve
        # the currently visible frame while the next one is prepared.
        ratio = self.devicePixelRatioF()
        available = self.screen().geometry()
        target = (round(available.width() * ratio), round(available.height() * ratio))
        self.background_generation = getattr(self, 'background_generation', 0) + 1
        generation = self.background_generation
        if isinstance(source, QPixmap):
            if source.isNull():
                self.transition_background(QPixmap())
                return
            source = source.toImage()
            key = None
        else:
            path = Path(source)
            if not path.is_file():
                self.transition_background(QPixmap())
                return
            key = (str(path), path.stat().st_mtime_ns, blur_radius, darkness, colour('#101112'), target)
        self.background_cache = getattr(self, 'background_cache', {})
        if key is not None and key in self.background_cache:
            self.transition_background(self.background_cache[key])
            return
        from .tasks import Task
        from .background_art import prepare
        base = colour('#101112')
        task = Task(lambda: prepare(source, blur_radius, base, darkness, target))
        self.background_tasks = getattr(self, 'background_tasks', [])
        self.background_tasks.append(task)
        def complete(image):
            from PyQt6 import sip
            if sip.isdeleted(self):
                self.background_tasks.remove(task)
                return
            pixmap = QPixmap.fromImage(image)
            if key is not None:
                self.background_cache[key] = pixmap
                # Keep viewport-sized artwork bounded even on high-DPI screens.
                while len(self.background_cache) > 1 and (len(self.background_cache) > 12 or
                        sum(p.width() * p.height() * 4 for p in self.background_cache.values()) > 96 * 1024 * 1024):
                    self.background_cache.pop(next(iter(self.background_cache)))
            if generation == self.background_generation:
                self.transition_background(pixmap)
            self.background_tasks.remove(task)
        def failed(error):
            from PyQt6 import sip
            if not sip.isdeleted(self) and generation == self.background_generation:
                self.transition_background(QPixmap())
            self.background_tasks.remove(task)
        task.signals.succeeded.connect(complete)
        task.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(task)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.background.isNull() and not self.previous_backgrounds:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for pixmap, opacity in [*self.previous_backgrounds, (self.background, self.background_mix)]:
            if opacity <= 0:
                continue
            painter.setOpacity(opacity)
            if pixmap.isNull():
                painter.fillRect(self.rect(), QColor(colour('#101112')))
                continue
            source = QRectF(pixmap.rect())
            aspect = self.width() / max(1, self.height())
            image_aspect = source.width() / max(1, source.height())
            if image_aspect > aspect:
                width = source.height() * aspect
                source.setX((source.width() - width) / 2)
                source.setWidth(width)
            else:
                height = source.width() / aspect
                source.setY((source.height() - height) / 2)
                source.setHeight(height)
            painter.drawPixmap(QRectF(self.rect()), pixmap, source)


def game_context_menu(parent, edit_handler, delete_handler, plugin_actions=(), open_folder_handler=None):
    menu = QMenu(parent)
    def add_entries(target, entries):
        for title, callback in entries:
            if isinstance(callback, (list, tuple)):
                add_entries(target.addMenu(title), callback)
            else:
                target.addAction(title).triggered.connect(callback)
    def populate():
        menu.clear()
        if edit_handler is not None:
            menu.addAction('Edit…').triggered.connect(edit_handler)
        if open_folder_handler is not None:
            menu.addAction('Open install folder').triggered.connect(open_folder_handler)
        menu.addSeparator()
        crack_tools = None
        for plugin_name, actions in (plugin_actions() if callable(plugin_actions) else plugin_actions):
            if actions:
                if plugin_name in ('SteamAutoCrack', 'GameCopyWorld'):
                    if crack_tools is None:
                        crack_tools = menu.addMenu('Crack Tools')
                    submenu = crack_tools.addMenu(plugin_name)
                else:
                    submenu = menu.addMenu(plugin_name)
                add_entries(submenu, actions)
        menu.addSeparator()
        menu.addAction('Delete…').triggered.connect(delete_handler)
    populate()
    if callable(plugin_actions):
        menu.aboutToShow.connect(populate)
    return menu


class Hero(QWidget):
    def __init__(self, play, edit_handler, delete_handler, plugin_actions=(), open_folder_handler=None):
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
        menu = game_context_menu(dropdown, edit_handler, delete_handler, plugin_actions, open_folder_handler)
        dropdown.setMenu(menu)
        split.addWidget(dropdown)
        self.position_play_control()

    def align_with_cover(self, cover_width):
        self.position_play_control()

    def position_play_control(self):
        padding = 8 if self.pixmap.isNull() else 24
        button = self.play_button
        button.ensurePolished()
        metrics = button.fontMetrics()
        option = QStyleOptionButton()
        option.initFrom(button)
        option.text = max(('Play', 'Stop', 'Stopping…', 'Launching…', 'Launching...'),
                          key=metrics.horizontalAdvance)
        content = QSize(metrics.horizontalAdvance(option.text), metrics.height())
        button_width = button.style().sizeFromContents(QStyle.ContentsType.CT_PushButton,
                                                      option, content, button).width()
        self.play_control.setFixedWidth(max(150, button_width + 30))
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
    layout.setContentsMargins(24, 24, 24, 24)
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
        from .rich_description import set_description_html
        set_description_html(self, content)

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


class DescriptionLinksLayout(QHBoxLayout):
    """Keep stretched geometry out of the page's natural height calculation."""
    def description(self):
        row = self.parentWidget()
        return row.description if getattr(row, 'wide', False) else None

    def sizeHint(self):
        size = super().sizeHint()
        description = self.description()
        if description is not None:size.setHeight(description.sizeHint().height())
        return size

    def minimumSize(self):
        size = super().minimumSize()
        description = self.description()
        if description is not None:size.setHeight(description.minimumSizeHint().height())
        return size

    def heightForWidth(self, width):
        description = self.description()
        return description.sizeHint().height() if description is not None else super().heightForWidth(width)


class DescriptionLinksRow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName('descriptionLinksRow')
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.columns = DescriptionLinksLayout(self)
        self.columns.setContentsMargins(0, 0, 0, 0)
        self.columns.setSpacing(24)
        self.links = None
        self.links_size = QSize()
        self.description = None
        self.link_scroll = None
        self.wide = None

    def set_columns(self, wide):
        if self.links is not None and self.description is None:
            wide = False
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
            self.links.setMinimumHeight(0)
            self.links.setMaximumHeight(16777215)
            self.links.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
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
