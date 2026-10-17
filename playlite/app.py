from .date_display import display_date
from .theme import colour, set_style
from .theme import apply as apply_theme, themed_asset
from .lifecycle import show_warning
from .desktop import open_folder
from .lifecycle import run_dialog
import argparse
import html
import json
import logging
import copy
import os
import shutil
import sys
from pathlib import Path

from .editor import MetadataEditor, save_game
from .artwork import repair_artwork
from .ui_style import DROPDOWN_STYLE
from .library import FILTER_FIELDS, SORT_FIELDS, query_games, filter_values
from .library_filters import LibraryFilter
from .scroll_fades import ContentFade, ScrollFades, HorizontalValuesScroll
from .link_names import load_names, friendly_name

from PyQt6.QtCore import QAbstractAnimation, QItemSelectionModel, Qt, QSize, QUrl, QTimer, QRect, QRectF, QSettings, QThreadPool, QEvent, QVariantAnimation, QEasingCurve, QElapsedTimer
from PyQt6.QtGui import QFontMetrics, QColor, QDesktopServices, QIcon, QImageReader, QCursor, QPainter, QPen, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QStyledItemDelegate, QStyleOptionViewItem, QStyleOptionButton, QStyle, QDialog, QDialogButtonBox, QFormLayout, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSplitter, QTextBrowser, QVBoxLayout, QBoxLayout, QWidget, QComboBox, QCheckBox, QGridLayout, QListView, QMenu, QAbstractItemView,
)

DATA = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'playlite'
STYLE = '''
QToolTip { background: #242527; color: #e9e9e9; border: 1px solid #62646a; border-radius: 6px; padding: 8px 12px; font-size: 13px; }
QWidget { background: #101112; color: #e9e9e9; font-family: "DejaVu Sans"; font-size: 13px; }
QWidget:disabled { color: #777; }
QCheckBox::indicator, QAbstractItemView::indicator { width: 14px; height: 14px; border: 1px solid #777; border-radius: 4px; background: #2c2d2f; }
QCheckBox::indicator:checked, QAbstractItemView::indicator:checked { border-color: #2196f3; background: #2196f3; image: url("{ASSET_DIR}/checkbox-check.svg"); }
QCheckBox::indicator:indeterminate, QAbstractItemView::indicator:indeterminate { border-color: #2196f3; background: #2196f3; image: url("{ASSET_DIR}/checkbox-partial.svg"); }
QCheckBox::indicator:disabled, QAbstractItemView::indicator:disabled { border-color: #404144; background: #292a2b; }
QCheckBox::indicator:checked:disabled, QAbstractItemView::indicator:checked:disabled { image: url("{ASSET_DIR}/checkbox-check-disabled.svg"); }
QMainWindow, QWidget#toolbar { background: #171819; }
QWidget#rail { background: #151617; border-right: 1px solid #252628; }
QLabel { background: transparent; }
QLabel#brand { color: #dc69a1; font-weight: bold; font-size: 22px; }
QLineEdit { background: #2c2d2f; border: 0; border-radius: 8px; padding: 8px 12px; }
QDialog QLineEdit, QDialog QComboBox, QDialog QSpinBox { min-height: 20px; border-radius: 8px; }
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
QPushButton:pressed { background: #292a2c; }
QPushButton:focus { border: 1px solid #2196f3; padding: 9px 17px; }
QPushButton[primary="true"] { background: #2196f3; color: @accent_text; font-weight: bold; }
QPushButton[primary="true"]:hover { background: #98caff; }
QPushButton[primary="true"]:pressed { background: #879bb7; }
QPushButton[primary="true"]:disabled { background: #292a2b; color: #777; }
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
QPushButton#play:disabled { color: #777; background: #292a2b; }
QPushButton:disabled { color: #777; background: #292a2b; }
QPushButton#link, QPushButton#folder { background: transparent; text-align: left; padding: 5px 0; }
QPushButton#link:hover, QPushButton#folder:hover { color: #98caff; }
QLabel#section { font-weight: bold; font-size: 15px; }
QLabel#muted { color: #999a9d; }
QSplitter::handle { background: #252628; width: 1px; }
QTextEdit { background: #2c2d2f; border: 1px solid #404144; border-radius: 6px; }
QComboBox { background: #2c2d2f; border: 0; border-radius: 6px; padding: 7px 10px; }
QComboBox QAbstractItemView { background: #242527; selection-background-color: #48494b; }
'''

STYLE += DROPDOWN_STYLE


STYLE = STYLE.replace('{ASSET_DIR}', (Path(__file__).parent / 'assets').as_posix())

# Keep the established imports available to plugins and callers.
from .game_view import (ArtworkPage, Hero, Description, LinkLayout, LinkContent,
    LinksScroll, RevealPanel, ResponsiveContent, DescriptionLinksLayout,
    DescriptionLinksRow, game_context_menu, label, card, horizontal_values)
from .library_list import (LibraryList, LibraryRowExpansion, CompactLibraryDelegate,
    selection_border, toolbar_icon)


class LibraryWindow(QMainWindow):
    def __init__(self, data):
        super().__init__()
        self.data = data
        from .background_tasks import BackgroundTasks
        self.background_tasks = BackgroundTasks(self, data / "background-tasks.json")
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
        self.size_tasks = {}
        self.stop_tasks = {}
        from .automation import Automation
        self.automation = Automation(self)
        QApplication.instance().aboutToQuit.connect(self.automation.cancel_all)
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
        self.setWindowTitle('Playlite (Repo)' if os.environ.get('PLAYLITE_PROFILE') == 'repo' else 'Playlite')
        screen = QApplication.primaryScreen()
        default_width = screen.availableGeometry().width() // 2 if screen else 1540
        self.fit_default_height = True
        self.default_window_height = 1140
        size = QSize(default_width, self.default_window_height)
        self.resize(size)
        self.last_normal_size = QSize(size)
        # Reserve status space before layout, even without a temporary message.
        self.statusBar().show()
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
        bar.setSpacing(4)
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
        from .background_tasks import show_tasks
        self.logo_menu.addAction('Background tasks…').triggered.connect(lambda: show_tasks(self))
        from .readiness import show_readiness
        self.logo_menu.addAction('Check library readiness…').triggered.connect(lambda: show_readiness(self,self.games))
        for plugin in self.generic_plugins:
            for action_label, callback in getattr(plugin, 'main_menu_actions', lambda window: [])(self):
                self.logo_menu.addAction(action_label).triggered.connect(callback)
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
        self.search.setMinimumWidth(100)
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
        self.sort.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.sort.setMinimumContentsLength(4)
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
            options = self.library_filter_options(key)
            selected = self.active_filters.get(key, [])
            if key == 'Source':
                selected = selected if isinstance(selected, list) else [selected] if selected else []
                labels = {label: value for label, value in options}
                selected = [labels.get(value, value) for value in selected]
            control = LibraryFilter(title, options, selected)
            control.changed.connect(self.refresh_library)
            self.filter_controls[key] = control
            filters_layout.addWidget(control, index // 4, index % 4)
        self.installed_filter = LibraryFilter('Installation states',
            [('Installed', 'Installed'), ('Not installed', 'Not installed')], self.active_filters.get('Installed', []))
        self.installed_filter.changed.connect(self.refresh_library)
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
        self.list.itemDoubleClicked.connect(self.play_game_entry)
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
        self.details.setSpacing(24)
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
        from .downloads import DownloadQueue, DownloadsPanel, DownloadsButton
        self.download_queue = DownloadQueue(self,self.data/'downloads.json')
        for plugin in self.generic_plugins:
            restore=getattr(plugin,'restore_downloads',None)
            if callable(restore):restore(self,self.download_queue)
        self.background_tasks.follow_downloads(self.download_queue)
        self.downloads_panel = DownloadsPanel(self.game_scroll, self.download_queue)
        self.downloads_button = DownloadsButton(toolbar, self.downloads_panel, self.download_queue, toolbar=True)
        self.downloads_button.button.setFixedSize(control_height, control_height)
        set_style(self.downloads_button.button, 'padding: 0;')
        toolbar.layout().addSpacing(12)
        toolbar.layout().addWidget(self.downloads_button.button)
        self.apply_panel_appearance()
        self.split.splitterMoved.connect(self.remember_library_width)
        self.configure_view()
        self.filter_games('')
        from .game_detection import GameDetection
        self.game_detection = GameDetection(self.game_providers, lambda: self.games, self,
                                            recorder=self.record_game_session)
        self.launched_actions = {}
        self.game_detection.session_finished.connect(self.game_session_finished)
        self.game_detection.changed.connect(self.game_status_changed)
        self.game_detection.start()
        for plugin in self.generic_plugins:
            QTimer.singleShot(0, lambda plugin=plugin: self.initialize_generic_plugin(plugin))

    def initialize_generic_plugin(self, plugin):
        try:
            plugin.library_ready(self)
        except Exception as error:
            self.statusBar().showMessage(f'{plugin.name}: {error}', 15000)


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
        self.active_filters = {key: control.values() for key, control in self.filter_controls.items()}
        self.active_filters.update(Installed=self.installed_filter.values(),
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
        self.update_game_count()
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
        self.game_background.update()
        self.update_library_scrollbar_policy()
        bar = self.game_scroll.verticalScrollBar()
        set_style(bar, '' if bar.maximum() > bar.minimum() else 'QScrollBar::handle:vertical { background: transparent; }')

    def apply_metadata_filter(self, key, value):
        control = self.filter_controls[key]
        if value not in control.boxes:
            control.set_options(control.options + [(str(value), value)], control.values())
        self.search.clear()
        control.set_values([value])
        self.set_filters_expanded(True)

    def reset_filters(self):
        controls = list(self.filter_controls.values()) + [self.installed_filter, self.favorites_filter, self.hidden_filter]
        for control in controls:
            control.blockSignals(True)
            if isinstance(control, LibraryFilter):
                control.set_values([])
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

    def library_filter_options(self, key):
        assigned = {value for game in self.games for value in filter_values(game, key)}
        labels = {provider.id: provider.name.removesuffix(' Integration') for provider in self.game_providers}
        options = [(labels.get(value, value.removesuffix('Integration')) if key == 'Source' else value, value)
                   for value in assigned]
        return [('None', None)] + sorted(options, key=lambda item: item[0].casefold())

    def update_filter_choices(self):
        for key, title in FILTER_FIELDS:
            control = self.filter_controls[key]
            selected = control.values()
            control.blockSignals(True)
            options = self.library_filter_options(key)
            control.set_options(options, selected)
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
            from PyQt6 import sip
            if isinstance(self, QWidget) and sip.isdeleted(self):
                return
            if generation != self.game_view_generation:
                return
            try:
                # Showing new children and sizing the header posts more layout
                # requests. Resolve these without processing any paint events.
                self.page.ensurePolished()
                for _ in range(1):
                    self.details.invalidate()
                    self.details.activate()
                    self.page.layout().activate()
                    QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
                self.game_scroll.verticalScrollBar().setValue(position)
            finally:
                self.game_scroll.setUpdatesEnabled(True)
        QTimer.singleShot(0, finish_switch)

    def load_detail_artwork(self, header_source, cover_source, hero, cover, row, information):
        ratio=self.devicePixelRatioF()
        from .detail_artwork import load
        from .tasks import Task
        cache=getattr(self,'detail_art_cache',None)
        if cache is None:cache=self.detail_art_cache={}
        key=(header_source,cover_source,ratio)
        # Modification timestamps are checked in the worker, not on every frame.
        def apply(images):
            from PyQt6 import sip
            if (isinstance(self, QWidget) and sip.isdeleted(self)
                    or isinstance(hero, QWidget) and sip.isdeleted(hero)
                    or self.play_hero is not hero):return
            header,poster=images
            hero.pixmap=QPixmap.fromImage(header)
            if not header.isNull():
                hero.setFixedHeight(max(240,round(self.content.width()*header.height()/header.width())))
            hero.update();hero.position_play_control()
            if not poster.isNull():
                pixmap=QPixmap.fromImage(poster);pixmap.setDevicePixelRatio(ratio)
                cover.setPixmap(pixmap);size=pixmap.deviceIndependentSize().toSize();cover.setFixedSize(size)
                row.setFixedHeight(size.height());information.setFixedHeight(size.height())
                hero.align_with_cover(size.width());self.content.update_cover()
        if key in cache:apply(cache[key])
        task=Task(lambda:load(header_source,cover_source,ratio))
        tasks=getattr(self,'detail_art_tasks',None)
        if tasks is None:tasks=self.detail_art_tasks=[]
        tasks.append(task)
        def loaded(images):
            if len(cache)>=12 and key not in cache:cache.pop(next(iter(cache)))
            cache[key]=images;apply(images);tasks.remove(task)
        task.signals.succeeded.connect(loaded)
        task.signals.failed.connect(lambda _:tasks.remove(task))
        QThreadPool.globalInstance().start(task)

    def build_game_view(self, item):
        self.play_hero = None
        self.details.setAlignment(Qt.AlignmentFlag.AlignTop)
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
                                           self.settings.value('appearance/backgroundBlur', 2.0, type=float),
                                           self.settings.value('appearance/backgroundDarken', 84, type=int))
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
        play.setEnabled(self.has_play_actions(game))
        play.clicked.connect(self.play_game)
        play.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        play.customContextMenuRequested.connect(lambda _position: self.play_game(choose_action=True))
        play.setToolTip('Play the default action. Right-click to choose a play action.')
        hero = Hero(play, self.edit_game, self.delete_game, lambda: self.plugin_game_actions(game),
                    (lambda: open_folder(game['InstallDirectory'])) if game.get('InstallDirectory') else None)
        self.play_hero = hero
        header_source = self.asset(game, 'HeaderImage' if 'HeaderImage' in game else 'BackgroundImage')
        hero.pixmap = QPixmap()
        if hero.pixmap.isNull():
            hero.setFixedHeight(max(240, round(self.content.width() * .5)) if header_source else hero.play_control.sizeHint().height() + 16)
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
        cover_source = self.asset(game, 'CoverImage')
        has_cover = bool(game.get('CoverImage'))
        if has_cover:
            self.content.cover = cover
            logical_size = QSize(190, 295)
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
            info.addWidget(horizontal_values([display_date(release)], 'muted', lambda value: self.apply_metadata_filter('ReleaseDate', release)))
        for key in ('Platforms', 'Genres'):
            values = game.get(key) or (['PC (Windows)'] if key == 'Platforms' else [])
            if values:
                info.addWidget(horizontal_values(values, 'muted', lambda value, key=key: self.apply_metadata_filter(key, value), separator=' · '))
        columns.addWidget(information, 1, Qt.AlignmentFlag.AlignTop)
        links_size = QSize(logical_size) if has_cover else QSize(190, panel_height)
        self.content.update_cover()
        self.load_detail_artwork(header_source, cover_source if has_cover else '', hero, cover, row, information)
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
            full_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            full_layout.addWidget(label('Description', 'section'))
            description_panel = CollapsibleDescription(full_description)
            description_panel.description.fill_available = True
            description_panel.description.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            description_panel.description.setMaximumHeight(16777215)
            full_layout.addWidget(description_panel, 1)
            description_row.description = full_card
            full_card.installEventFilter(description_row)
            description_columns.addWidget(full_card, 1)
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
            description_columns.addWidget(links, 0)
        if game.get('FullDescription') or game.get('Links'):
            if description_row.description is not None:
                description_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                self.details.setAlignment(Qt.AlignmentFlag(0))
            self.details.addWidget(description_row, 1 if description_row.description is not None else 0)
            self.content.description_links_row = description_row
            self.content.update_cover()
        else:
            description_row.deleteLater()
        installation_row = DescriptionLinksRow()
        installation_row.setObjectName('installationRow')
        installation, folder_layout = card()
        installation.setProperty('installationPanel', True)
        heading = QHBoxLayout()
        heading.addWidget(label('Installation', 'section'))
        heading.addStretch()
        folder_layout.addLayout(heading)
        installation_form = QFormLayout()
        installation_form.setHorizontalSpacing(22)
        installation_form.setVerticalSpacing(8)
        installation_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        installation_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for plugin in self.generic_plugins:
            plugin.augment_game_view(self, game, heading, installation_form)
        if game.get('InstallDirectory'):
            from .ui_style import PathButton
            folder = PathButton(game['InstallDirectory'])
            folder.setObjectName('folder')
            folder.clicked.connect(lambda: open_folder(game['InstallDirectory']))
            set_style(folder, 'QPushButton#folder { padding: 0; }')
            folder.setFixedHeight(folder.fontMetrics().height())
            folder.setToolTip(game['InstallDirectory'])
            folder_scroll = HorizontalValuesScroll()
            set_style(folder_scroll, 'QScrollArea, QScrollArea > QWidget { background: transparent; border: 0; }')
            folder_scroll.setFrameShape(QFrame.Shape.NoFrame)
            folder_scroll.viewport().setAutoFillBackground(False)
            folder_scroll.setWidget(folder)
            folder_scroll.setWidgetResizable(True)
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
            self.history_labels['Last played'].setText(display_date(stamp))

    def game_session_finished(self, game_id):
        action = self.launched_actions.pop(game_id, None)
        game = next((entry for entry in self.games if entry['Id'] == game_id), None)
        if game is None:
            automation = getattr(self, 'automation', None)
            if automation is not None: automation.exited(game_id, lambda: None)
            return
        def notify_plugins():
            for plugin in self.generic_plugins:
                try:
                    plugin.after_game_stopped(self, copy.deepcopy(game), copy.deepcopy(action))
                except Exception:
                    import logging
                    logging.exception('Plugin %s failed after game exit', plugin.id)
        automation = getattr(self, 'automation', None)
        if automation is not None: automation.exited(game_id, notify_plugins)
        else: notify_plugins()

    def game_status_changed(self, game_id, status):
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item.data(Qt.ItemDataRole.UserRole)['Id'] == game_id:
                item.setToolTip(status if status in ('Running', 'Launching', 'Launch failed') else '')
        if self.current and self.current['Id'] == game_id:
            stopping = game_id in self.stop_tasks
            preparing = self.automation.busy(game_id)
            self.play_button.setText('Preparing…' if preparing == 'before_launch' else 'Finishing…' if preparing == 'after_exit' else 'Stopping…' if stopping else 'Stop' if status == 'Running' else 'Launching…' if status == 'Launching' else 'Play')
            self.play_button.setEnabled(not stopping and not preparing and status != 'Launching' and
                                        (status == 'Running' or self.has_play_actions(self.current)))
            self.play_hero.position_play_control()

    def apply_panel_appearance(self):
        self.downloads_panel.set_transparency(self.settings.value('appearance/downloadsPanelTransparency', 0, type=int))
        self.list.panel_transparency = max(0, min(100, self.settings.value('appearance/sidePanelTransparency', 0, type=int)))
        self.list.viewport().setAutoFillBackground(False)
        self.list.update_scrollbar_padding()
        transparency = max(0, min(100, self.settings.value('appearance/gamePanelTransparency', 0, type=int)))
        alpha = round(255 * (1 - transparency / 100))
        if self.settings.value('appearance/readablePanels', True, type=bool) and alpha:
            alpha = max(204, alpha)
        panels=[]
        for index in range(self.details.count()):
            widget=self.details.itemAt(index).widget()
            if widget is not None:
                if isinstance(widget,QFrame):panels.append(widget)
                panels.extend(widget.findChildren(QFrame))
        for panel in panels:
            if panel.objectName() == 'card':
                set_style(panel, f'QFrame#card {{ background: rgba(29, 30, 32, {alpha}); border-radius: 16px; }}')

    def show_installation_size(self, game):
        from .installation import installation_size, format_size, record_installation_size
        from .tasks import Task
        directory = game['InstallDirectory']
        size = game.get('InstallSize')
        if size is None:
            size = self.installation_sizes.get(directory)
        if isinstance(size, (int, float)) and size >= 0:
            self.installation_size_label.setText(format_size(size))
            return
        if not Path(directory).is_dir():
            self.installation_size_label.setText('Size unavailable')
            return
        if directory in self.size_tasks:
            return
        task = Task(lambda: installation_size(directory))
        self.size_tasks[directory] = task
        def complete(value):
            self.size_tasks.pop(directory, None)
            self.installation_sizes[directory] = value
            try:
                self.games = record_installation_size(self.data, self.games, directory, value)
            except (OSError, ValueError):
                logging.exception('Could not save installation size for %s', directory)
            if self.current:
                self.current = next((entry for entry in self.games if entry['Id'] == self.current['Id']), None)
            for editor in self.findChildren(MetadataEditor):
                if (editor.isVisible() and editor.fields['InstallDirectory'].text().strip() == directory
                        and not editor.fields['InstallSize'].text().strip()):
                    editor.fields['InstallSize'].setText(str(value))
            if self.current and self.current.get('InstallDirectory') == directory:
                self.installation_size_label.setText(format_size(value))
        def failed(error):
            self.size_tasks.pop(directory, None)
            if self.current and self.current.get('InstallDirectory') == directory:
                self.installation_size_label.setText('Size unavailable')
        task.bind(self, complete, failed)
        QThreadPool.globalInstance().start(task)

    def has_play_actions(self, game):
        from .play_actions import actions_for
        available = {provider.id for provider in self.game_providers}
        return any(action.get('Integration') in available for action in actions_for(game, self.game_providers))

    def play_game_entry(self, item):
        if item is not self.list.currentItem():
            self.list.setCurrentItem(item)
        if (self.current and self.has_play_actions(self.current) and
                self.game_detection.status(self.current['Id']) not in ('Running', 'Launching') and
                self.current['Id'] not in self.stop_tasks):
            self.play_game()

    def play_game(self, checked=False, *, choose_action=False):
        if self.current is None:
            return
        automation = getattr(self, 'automation', None)
        if automation is not None and automation.busy(self.current['Id']):
            return
        if self.game_detection.status(self.current['Id']) == 'Running':
            if not choose_action:self.stop_game()
            return
        if self.game_detection.status(self.current['Id']) == 'Launching':
            return
        try:
            game = dict(self.current)
            from .play_actions import actions_for
            actions = actions_for(game, self.game_providers)
            if not actions:
                raise ValueError('Add a play action on the Installation page.')
            default = next((item for item in actions if item.get('Default') is True), None)
            action = default or actions[0]
            if choose_action or (len(actions) > 1 and default is None):
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
            from .installation_health import check_action
            health = check_action(game, action, self.game_providers, getattr(self, "download_queue", None))
            if health['issues']:
                raise ValueError('Installation needs attention:\n' + '\n'.join(health['issues']) + '\nReview the Installation page before launching.')
            for plugin in self.generic_plugins:
                if not plugin.before_launch(self, game):
                    return
                before_action = getattr(plugin, 'before_action_launch', None)
                if callable(before_action) and not before_action(self, game, action):
                    return
            game = copy.deepcopy(next(entry for entry in self.games if entry['Id'] == game['Id']))
            automation_action = copy.deepcopy(action)
            if automation is not None and action.get('Integration') == 'LutrisIntegration' and callable(getattr(provider, 'launch_configuration', None)) and (action.get('Prefix') or str(action.get('Executable', '')).lower().endswith('.exe')):
                configuration = provider.launch_configuration(action.get('GameId')).get('game') or {}
                automation_action['Prefix'] = configuration.get('prefix') or action.get('Prefix') or ''
                automation_action['InstallDirectory'] = configuration.get('working_dir') or action.get('InstallDirectory') or game.get('InstallDirectory') or ''
            def launch():
                try:
                    if not any(entry['Id'] == game['Id'] for entry in self.games):
                        raise ValueError('The game was removed while preparing to launch.')
                    health = check_action(game, action, self.game_providers, getattr(self, 'download_queue', None))
                    if health['issues']:
                        raise ValueError('Installation needs attention:\n' + '\n'.join(health['issues']))
                    from .providers import IntegrationPlugin
                    if isinstance(provider, IntegrationPlugin):
                        self.game_detection.launching(game['Id'])
                    provider.launch_action(game, action)
                    self.launched_actions[game['Id']] = copy.deepcopy(action)
                    for plugin in self.generic_plugins:
                        try:
                            plugin.after_launch(self, copy.deepcopy(game), copy.deepcopy(action))
                        except Exception:
                            import logging
                            logging.exception('Plugin %s failed after launch', plugin.id)
                    if automation is not None:
                        automation.launched(game, automation_action)
                except Exception as error:
                    self.game_detection.launch_failed(game['Id'])
                    show_warning(self, 'Cannot launch game', str(error))
            if automation is not None:
                automation.run(game, automation_action, 'before_launch', completed=launch)
            else:
                launch()

        except Exception as error:
            self.game_detection.launch_failed(game['Id'])
            show_warning(self, 'Cannot launch game', str(error))

    def stop_game(self):
        game = dict(self.current)
        identity = game['Id']
        if identity in self.stop_tasks:
            return
        dialog = QMessageBox(QMessageBox.Icon.Question, 'Stop game',
                             f'Stop “{game["Name"]}”? Unsaved progress may be lost.',
                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, self)
        dialog.button(QMessageBox.StandardButton.Yes).setText('Stop')
        dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if run_dialog(dialog) != QMessageBox.StandardButton.Yes:
            return
        from .tasks import Task
        from .providers import IntegrationPlugin
        def stop():
            providers = [provider for provider in self.game_providers
                         if isinstance(provider, IntegrationPlugin) and provider.owns(game)
                         and identity in provider.detect_running([game])]
            if not providers:
                raise ValueError('No running game process could be identified.')
            count = sum(provider.stop(game) for provider in providers)
            if not count:
                raise ValueError('The game process has already exited or could not be identified.')
        task = Task(stop)
        self.stop_tasks[identity] = task
        self.game_status_changed(identity, self.game_detection.status(identity))
        def finish(error=None):
            self.stop_tasks.pop(identity, None)
            self.game_status_changed(identity, self.game_detection.status(identity))
            if error:
                show_warning(self, 'Cannot stop game', error)
        task.signals.succeeded.connect(lambda _: finish())
        task.signals.failed.connect(finish)
        QThreadPool.globalInstance().start(task)

    def plugin_game_actions(self, game):
        from .installation_health import show_health
        from .readiness import show_readiness, grouped_actions
        actions=grouped_actions(self.generic_plugins,self,[game])
        installation=[('Ready to play…',lambda:show_readiness(self,[game])),('Check installation…',lambda:show_health(self,[game]))]
        existing=next((items for name,items in actions if name=='Installation'),[])
        return [('Installation',installation+existing)]+[(name,items) for name,items in actions if name!='Installation']

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
                    self.games = editor.persist(lambda game: save_game(self.data, self.games, game))
                except Exception as error:
                    editor.error.setText(f'Could not save the Playlite entry: {error}')
                    continue
                self.focus_added_game(editor.result_game['Id'])
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
        progress = self.library_animation.easingCurve().valueForProgress(
            self.library_animation.currentTime() / max(1, self.library_animation.duration()))
        for identity, (start, end) in getattr(self, 'transition_rows', {}).items():
            self.list.row_widths[identity] = start + (end - start) * progress
        self.list.fit_compact_width()

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
        for identity, (_, end) in getattr(self, 'transition_rows', {}).items():
            self.list.row_widths[identity] = end
        self.transition_rows = {}
        self.list.width_transition = False
        if self.compact_library:
            self.list.setFixedWidth(self.list.compact_width())
        else:
            self.list.setMinimumWidth(160)
            self.list.setMaximumWidth(16777215)
            self.restore_library_width()
        if not self.compact_library:
            self.list.hide_hover_immediately()
        self.list.fit_compact_width()
        self.list.viewport().update()
        self.update_library_scrollbar_policy()

    def update_game_count(self):
        selected = len(self.list.selectedItems())
        self.count.setText(f'{selected} / {self.list.count()} selected' if selected > 1
                           else f'{self.list.count()} / {len(self.games)} games')

    def update_compact_library(self):
        if not hasattr(self, 'list'):
            return
        self.update_game_count()
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
        if changed and not animate:
            self.list.hide_hover_immediately()
        if animate:
            self.transition_rows = {}
            current = self.list.currentItem()
            full_width = max(64, self.library_widths['list'] - self.list.compact_width() + 64)
            for animation in self.list.row_animations.values():
                animation.stop()
            for index in range(self.list.count()):
                item = self.list.item(index)
                game = item.data(Qt.ItemDataRole.UserRole)
                identity = game['Id']
                active = item.isSelected() or item is current or identity == self.list.hover_id
                start = self.list.row_widths.get(identity, 0)
                if compact and not start and active:
                    start = max(64, start_width - self.list.compact_width() + 64)
                if not start and not active:
                    continue
                if compact:
                    end = self.list.expanded_row_width(game) if identity == self.list.hover_id or item.isSelected() and self.list.has_multiple_selection() else (64 if active else 0)
                else:
                    end = full_width if active else 0
                self.transition_rows[identity] = (start or 64, end)
                self.list.row_widths[identity] = start or 64
            if self.list.expansion_layer is None:
                self.list.expansion_layer = LibraryRowExpansion(self.list)
            self.list.fit_compact_width()
            target = self.list.compact_width() if compact else self.library_widths['grid' if self.is_grid else 'list']
            self.library_animation.blockSignals(True)
            self.library_animation.setCurrentTime(0)
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

    def preload_ui(self, ready):
        """Settle the initial artwork and layout before exposing the window."""
        self.ensurePolished()
        timer = QTimer(self)
        timer.setInterval(16)
        self.startup_timer = timer
        def finish():
            if (getattr(self, 'detail_art_tasks', []) or
                    getattr(self.game_background, 'background_tasks', [])):
                return
            timer.stop()
            self.game_background.background_fade.stop()
            self.game_background.finish_background_fade()
            self.fit_default_height = False
            # Hidden widgets need explicit layout activation before measuring.
            for widget in [self, *self.findChildren(QWidget)]:
                if widget.layout() is not None:
                    widget.layout().activate()
            self.fit_content_height(False)
            for widget in [self, *self.findChildren(QWidget)]:
                if widget.layout() is not None:
                    widget.layout().activate()
            # Populate paint caches offscreen; the first visible frame is complete.
            self.grab()
            ready()
            timer.deleteLater()
        timer.timeout.connect(finish)
        timer.start()

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
        required = min(required, self.default_window_height)
        screen = self.screen()
        if screen:
            decoration = max(0, self.frameGeometry().height() - self.height())
            required = min(required, round(screen.availableGeometry().height() * 0.9) - decoration)
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
        if not self.download_queue.confirm_close(self):
            event.ignore();return
        self.download_queue.shutdown()
        if hasattr(self, 'selection_settings_timer'):
            self.selection_settings_timer.stop()
        self.game_detection.stop()
        self.save_window_state()
        super().closeEvent(event)

    def open_get_started(self):
        from .installer import InstallerDialog
        active = next((dialog for dialog in self.findChildren(InstallerDialog) if dialog.isVisible()), None)
        if active:
            active.raise_()
            active.activateWindow()
            return
        run_dialog(InstallerDialog(self, self.settings))

    def clear_play_progress(self):
        from .game_detection import clear_play_progress
        import time
        self.games = clear_play_progress(self.data, self.games)
        # Running games begin accruing fresh history from the reset time.
        now = time.monotonic()
        for session in self.game_detection.sessions.values():
            session.update(start=now, saved=0, counted=False, checkpoint=now)
        for identity in self.game_detection.missing:
            self.game_detection.missing[identity] = now
        self.refresh_library()

    def open_settings(self):
        from .settings import SettingsDialog
        active = next((dialog for dialog in self.findChildren(SettingsDialog) if dialog.isVisible()), None)
        if active:
            active.raise_()
            active.activateWindow()
            return
        if run_dialog(SettingsDialog(self.settings, self, clear_progress=self.clear_play_progress)) == QDialog.DialogCode.Accepted:
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

    def focus_added_game(self, identity):
        self.search.clear()
        self.update_filter_choices()
        self.refresh_library()
        def find_item():
            return next((self.list.item(index) for index in range(self.list.count())
                         if self.list.item(index).data(Qt.ItemDataRole.UserRole)['Id'] == identity), None)
        item = find_item()
        if item is None:
            self.reset_filters()
            item = find_item()
            if item is None and any(game['Id'] == identity and game.get('Hidden') for game in self.games):
                self.hidden_filter.setChecked(True)
                item = find_item()
        if item is not None:
            self.list.setCurrentItem(item, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            self.list.scrollToItem(item)
            self.list.setFocus(Qt.FocusReason.OtherFocusReason)

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
                self.games = dialog.persist(lambda game: save_game(self.data, self.games, game))
            except Exception as error:
                dialog.error.setText(f'Could not save the Playlite entry: {error}')
                continue
            self.focus_added_game(dialog.result_game['Id'])
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
        from .readiness import grouped_actions, show_readiness
        actions = self.plugin_game_actions(games[0]) if len(games) == 1 else grouped_actions(self.generic_plugins,self,games)
        from .installation_health import show_health
        if len(games) > 1:
            actions.append(('Installation', [('Ready to play…',lambda:show_readiness(self,games)),('Check installations…', lambda: show_health(self, games))]))
        menu = game_context_menu(self.list, self.edit_game if len(games) == 1 else None,
                                 lambda: self.delete_games(games), actions,
                                 (lambda: open_folder(games[0]['InstallDirectory']))
                                 if len(games) == 1 and games[0].get('InstallDirectory') else None)
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
        for game in games:
            for plugin in self.generic_plugins:
                try:
                    plugin.after_game_removed(self, copy.deepcopy(game))
                except Exception as error:
                    self.statusBar().showMessage(f'{plugin.name}: {error}', 15000)
        self.update_filter_choices()
        self.refresh_library()

    def edit_game(self):
        active = next((dialog for dialog in self.findChildren(QDialog) if dialog.isVisible()), None)
        if active:
            active.raise_()
            active.activateWindow()
            return
        # Keep navigation stable even if editing a name changes the sort order.
        order = [self.list.item(index).data(Qt.ItemDataRole.UserRole)['Id']
                 for index in range(self.list.count())]
        if self.current is None:
            return
        if self.current['Id'] not in order:
            order = [self.current['Id']]
        position = order.index(self.current['Id'])
        shell = QDialog(self)
        shell.setProperty('playliteLayoutReady', True)
        body = QVBoxLayout(shell)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        state = {'editor': None}

        def load(target, tab=0):
            editor = MetadataEditor(target, self.data, self)
            editor.set_game_navigation(position, len(order))
            editor.setProperty('playliteLayoutReady', True)
            editor.setWindowFlags(Qt.WindowType.Widget)
            editor.setParent(shell)
            editor.tabs.setCurrentIndex(tab)
            editor.save_handler = persist
            editor.rejected.connect(shell.reject)
            old = state['editor']
            if old is not None:
                body.removeWidget(old)
                old.hide()
                old.cleanup_downloads()
                old.deleteLater()
            else:
                shell.resize(editor.size())
            state['editor'] = editor
            shell.setWindowTitle(editor.windowTitle())
            body.addWidget(editor)
            editor.show()

        def persist(offset):
            nonlocal position
            editor = state['editor']
            try:
                save = lambda: save_game(self.data, self.games, editor.result_game)
                self.games = editor.play_actions.save_with_removals(save, editor.result_game) if hasattr(editor, 'play_actions') else save()
            except (OSError, ValueError) as error:
                editor.error.setText(f'Could not save game: {error}')
                return
            for cache in editor.download_caches:
                cache.cleanup()
            editor.download_caches.clear()
            for plugin in self.generic_plugins:
                try:
                    plugin.after_game_updated(self, editor.result_game)
                except Exception as error:
                    self.statusBar().showMessage(f"Could not update {plugin.name}: {error}", 10000)
            self.update_filter_choices()
            if not offset:
                self.refresh_library()
                shell.accept()
                return
            target_position = position + offset
            target = next((game for game in self.games if game['Id'] == order[target_position]), None)
            if target is None:
                editor.error.setText('The adjacent game is no longer in the library.')
                return
            position = target_position
            tab = editor.tabs.currentIndex()
            self.current = target
            self.refresh_library()
            load(target, tab)

        load(self.current)
        run_dialog(shell)
        state['editor'].cleanup_downloads()
        shell.deleteLater()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=DATA)
    parser.add_argument('--screenshot', type=Path, help='Render an offscreen preview and exit.')
    args = parser.parse_args()
    app = QApplication(['playlite'])
    from .native_style import configure
    configure(app)
    app.setApplicationName('playlite')
    repo_profile = os.environ.get('PLAYLITE_PROFILE') == 'repo'
    app.setApplicationDisplayName('Playlite (Repo)' if repo_profile else 'Playlite')
    app.setDesktopFileName('playlite-dev' if repo_profile else 'playlite')
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
    def reveal():
        window.show()
        if args.screenshot:
            window.grab().save(str(args.screenshot))
            app.quit()
        elif not window.settings.value('onboarding/completed', False, type=bool):
            QTimer.singleShot(0, window.open_get_started)
    window.preload_ui(reveal)
    sys.exit(app.exec())
