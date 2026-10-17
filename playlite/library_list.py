"""Library list/grid painting, hover transitions, and compact view geometry."""
from PyQt6.QtCore import (Qt, QSize, QRect, QRectF, QEvent, QVariantAnimation,
    QEasingCurve, QElapsedTimer, QAbstractAnimation, QTimer)
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QColor, QPen, QPainterPath, QFontMetrics, QCursor
from PyQt6.QtWidgets import (QWidget, QListWidget, QListView, QStyledItemDelegate,
    QStyleOptionViewItem, QStyle)
from .theme import colour, set_style
from .scroll_fades import ContentFade, ScrollFades


def toolbar_icon(kind):
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
        game_id = (index.data(Qt.ItemDataRole.UserRole) or {}).get('Id')
        if view.width_transition and view.row_widths.get(game_id, 0) > 0:
            return  # The expansion layer carries this row through the transition.
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
        self.area = view
        self.horizontal = False
        self.edge_fade = ContentFade(self)
        self.setGraphicsEffect(self.edge_fade)
        view.viewport().installEventFilter(self)
        view.verticalScrollBar().valueChanged.connect(self.edge_fade.update)
        view.verticalScrollBar().rangeChanged.connect(self.edge_fade.update)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        set_style(self, 'background: transparent;')

    def update_bounds(self):
        viewport = self.view.viewport()
        origin = self.parentWidget().mapFromGlobal(viewport.mapToGlobal(viewport.rect().topLeft()))
        # Allow horizontal expansion over details, but never outside the list's
        # vertical viewport (including its toolbar and status-bar boundaries).
        self.setGeometry(0, origin.y(), self.parentWidget().width(), viewport.height())

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show):
            self.update_bounds()
        return False

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
            origin = self.mapFromGlobal(self.view.viewport().mapToGlobal(row.topLeft()))
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
        self.fades = ScrollFades(self)
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
        if self.compact_enabled and not self.width_transition:
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
            self.expansion_layer.update_bounds()
            self.expansion_layer.setVisible((self.compact_enabled or self.width_transition) and any(width > 0 for width in self.row_widths.values()))
            self.expansion_layer.raise_()
            self.expansion_layer.update()
        self.viewport().update()

    def expanded_row_width(self, game):
        width = 64 + self.fontMetrics().horizontalAdvance(game['Name']) + 14
        return min(width, max(64, self.window().width() - 250))

    def animate_row(self, game_id, target):
        if self.width_transition:
            return
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
