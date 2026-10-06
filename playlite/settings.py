from .theme import set_style
from .ui_style import DROPDOWN_STYLE
"""Application preferences and metadata-provider configuration."""
from pathlib import Path
import os
import json
from PyQt6.QtCore import QUrl, Qt, QItemSelectionModel
from PyQt6.QtGui import QDesktopServices, QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (QMenu, QCheckBox, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QToolButton,
                             QPlainTextEdit, QFormLayout, QGridLayout, QFrame, QPushButton, QLabel, QLineEdit, QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout, QWidget, QSlider, QHBoxLayout, QColorDialog, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView)
from .theme import ROLES, palette, base_palette, apply as apply_theme
from .image_filters import OPTIONS, defaults as image_filter_defaults, FilterChecks
from .lifecycle import run_dialog
from .desktop import open_folder
from .link_names import load_names, LinkNamesDialog


class SettingsSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None, metadata=False):
        super().__init__(parent)
        self.settings = settings
        self.link_names = load_names(settings)
        self.setWindowTitle('Playlite Settings')
        set_style(self, DROPDOWN_STYLE + """
QFrame#settingsCard { background: #1d1e20; border: 1px solid #252628; border-radius: 12px; }
QFrame#settingsCard QCheckBox, QFrame#settingsCard QSlider, QWidget#colourField { background: transparent; }
QFrame#settingsCard QSlider::groove:horizontal { height: 5px; background: #404144; border-radius: 2px; }
QFrame#settingsCard QSlider::sub-page:horizontal { background: #2196f3; border-radius: 2px; }
QFrame#settingsCard QSlider::handle:horizontal { background: #e9e9e9; width: 14px; margin: -5px 0; border-radius: 7px; }
QLabel#settingsHeading { font-weight: bold; font-size: 16px; }
QLabel#settingsHint { color: #999a9d; }
QLabel#sliderHint { color: #68696c; }
QLabel#sliderValue { background: #2c2d2f; border-radius: 6px; padding: 4px 8px; }
QPushButton#colourSwatch { text-align: left; padding: 6px 8px; }
QScrollArea#settingsScroll { border: none; background: #101112; }
QScrollArea#settingsScroll > QWidget { background: transparent; }
QScrollArea#settingsScroll QScrollBar,
QScrollArea#settingsScroll QScrollBar::add-page,
QScrollArea#settingsScroll QScrollBar::sub-page { background: transparent; }
""")
        available_height = self.screen().availableGeometry().height() - 80
        self.resize(820, min(800, max(400, available_height)))
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        self.tabs = tabs
        layout.addWidget(tabs)
        def page(title, description):
            content = QWidget()
            body = QVBoxLayout(content)
            body.setContentsMargins(20, 20, 20, 20)
            body.setSpacing(16)
            heading = QLabel(title)
            heading.setObjectName('settingsHeading')
            body.addWidget(heading)
            body.addWidget(self.hint(description))
            area = QScrollArea()
            area.setObjectName('settingsScroll')
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.Shape.NoFrame)
            area.viewport().setAutoFillBackground(False)
            area.setWidget(content)
            tabs.addTab(area, title)
            return body

        general = page('General', 'Choose how Playlite opens and behaves when you close it.')
        installation = self.card(general, 'Installation')
        installation.addWidget(QLabel('Default installation folder'))
        self.default_install_folder = QLineEdit(settings.value('installation/defaultFolder', '', type=str))
        browse_install = QPushButton('Browse…')
        def choose_install_folder():
            from .lifecycle import choose_directory
            folder=choose_directory(self,'Default installation folder',self.default_install_folder.text())
            if folder:self.default_install_folder.setText(folder)
        browse_install.clicked.connect(choose_install_folder)
        install_row=QHBoxLayout();install_row.setSpacing(10)
        install_row.addWidget(self.default_install_folder,1);install_row.addWidget(browse_install)
        installation.addLayout(install_row)
        installation.addWidget(self.hint('Add Game browses from this folder. Plugin-specific installation folders take precedence.'))
        installation.addWidget(QLabel('Default Wine prefix parent folder'))
        self.default_prefix_folder = QLineEdit(settings.value('installation/defaultPrefixFolder', '', type=str))
        browse_prefix = QPushButton('Browse…')
        def choose_prefix_folder():
            from .lifecycle import choose_directory
            folder = choose_directory(self, 'Default Wine prefix parent folder', self.default_prefix_folder.text())
            if folder:
                self.default_prefix_folder.setText(folder)
        browse_prefix.clicked.connect(choose_prefix_folder)
        prefix_row = QHBoxLayout()
        prefix_row.setSpacing(10)
        prefix_row.addWidget(self.default_prefix_folder, 1)
        prefix_row.addWidget(browse_prefix)
        installation.addLayout(prefix_row)
        installation.addWidget(self.hint('Installation plugins can create separate Wine prefixes under this folder. Plugin-specific prefix folders take precedence.'))
        updates = self.card(general, 'Updates')
        from importlib.metadata import version, PackageNotFoundError
        try:
            current_version = version('playlite')
        except PackageNotFoundError:
            current_version = 'repo checkout'
        self.application_version = current_version
        self.update_status = QLabel('Current version: ' + current_version)
        self.update_status.setWordWrap(True)
        updates.addWidget(self.update_status)
        self.check_update_button = QPushButton('Check for updates')
        self.install_update_button = QPushButton('Install update and restart')
        self.install_update_button.setEnabled(False)
        self.check_update_button.clicked.connect(self.check_application_update)
        self.install_update_button.clicked.connect(self.install_application_update)
        update_row = QHBoxLayout()
        update_row.addWidget(self.check_update_button)
        update_row.addWidget(self.install_update_button)
        updates.addLayout(update_row)
        updates.addWidget(self.hint('Updates retain your library, settings, and plugins. Repo builds are updated through Git. Update output is saved to update.log in this profile’s Playlite data folder.'))
        startup = self.card(general, 'Startup')
        self.default_view = QComboBox()
        for title, value in [('Grid', 'grid'), ('List', 'list'), ('Compact list', 'compact'), ('Remember last', 'remember')]:
            self.default_view.addItem(title, value)
        self.default_view.setCurrentIndex(max(0, self.default_view.findData(settings.value('app/defaultView', 'remember'))))
        self.default_view.setMinimumWidth(190)
        view_row = QHBoxLayout()
        view_row.setSpacing(16)
        view_row.addWidget(QLabel('Default library view'))
        view_row.addWidget(self.default_view)
        view_row.addStretch()
        startup.addLayout(view_row)
        startup.addWidget(self.hint('The view shown when you open Playlite.'))
        self.reset_on_launch = QCheckBox('Reset sorting and filters on launch')
        self.reset_on_launch.setChecked(settings.value('app/resetSortingFilters', False, type=bool))
        startup.addWidget(self.reset_on_launch)
        startup.addWidget(self.hint('Start with the full library instead of restoring your last filters.'))
        behaviour = self.card(general, 'Window behaviour')
        self.close_to_tray = QCheckBox('Close to system tray')
        self.close_to_tray.setChecked(settings.value('app/closeToTray', True, type=bool))
        behaviour.addWidget(self.close_to_tray)
        behaviour.addWidget(self.hint('Keep Playlite running in the system tray when you close the main window.'))
        descriptions = self.card(general, 'Descriptions')
        self.hide_description_overlap = QCheckBox('Hide repeated short-description sentences in the long description')
        self.hide_description_overlap.setChecked(settings.value('descriptions/hideRepeatedSentences', False, type=bool))
        descriptions.addWidget(self.hide_description_overlap)
        descriptions.addWidget(self.hint('Hide identical sentences in the game view. Saved descriptions stay unchanged.'))
        links = self.card(general, 'Links')
        links.addWidget(self.hint('Set friendly names for website links in the game view.'))
        self.link_names_button = QPushButton('Link names…')
        self.link_names_button.clicked.connect(self.edit_link_names)
        links.addWidget(self.link_names_button, alignment=Qt.AlignmentFlag.AlignLeft)
        general.addStretch()

        appearance = page('Appearance', 'Adjust the background, panel transparency, and interface colours.')
        background = self.card(appearance, 'Background and panels')
        self.background_blur = SettingsSlider(Qt.Orientation.Horizontal)
        self.background_blur.setRange(0, 100)
        self.background_blur.setValue(settings.value('appearance/backgroundBlur', 48, type=int))
        self.background_blur_value = QLabel(str(self.background_blur.value()))
        self.background_blur.valueChanged.connect(lambda value: self.background_blur_value.setText(str(value)))

        def slider_field(label, slider, value_label, help_text):
            title_row = QHBoxLayout()
            title_row.addWidget(QLabel(label))
            title_row.addStretch()
            value_label.setObjectName('sliderValue')
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setMinimumWidth(58)
            title_row.addWidget(value_label)
            background.addLayout(title_row)
            background.addWidget(slider)
            background.addWidget(self.hint(help_text, 'sliderHint'))

        slider_field('Background blur', self.background_blur, self.background_blur_value,
                     'No blur at 0 · Maximum blur at 100')
        self.panel_transparency = {}
        for key, label, hint in [
                ('sidePanelTransparency', 'Side panel transparency', 'Library navigation background'),
                ('gamePanelTransparency', 'Game panel transparency', 'Detail panels; artwork and icons stay opaque'),
                ('downloadsPanelTransparency', 'Downloads panel transparency', 'Download panel and active download strip; controls stay opaque')]:
            slider = SettingsSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(settings.value(f'appearance/{key}', 0, type=int))
            value_label = QLabel(f'{slider.value()}%')
            slider.valueChanged.connect(lambda value, label=value_label: label.setText(f'{value}%'))
            slider_field(label, slider, value_label, hint + ' · 0% opaque / 100% transparent')
            self.panel_transparency[key] = slider

        from .providers import discover_plugins, ThemePlugin
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel('Theme'))
        self.theme_source = QComboBox()
        self.theme_source.addItem('Playlite default', '')
        for plugin in discover_plugins().values():
            if isinstance(plugin, ThemePlugin):
                self.theme_source.addItem(plugin.name, plugin.id)
        self.theme_source.setCurrentIndex(max(0, self.theme_source.findData(settings.value('appearance/theme', ''))))
        theme_row.addWidget(self.theme_source)
        theme_row.addStretch()
        appearance.addLayout(theme_row)
        self.colour_buttons = {}
        saved_palette = palette(settings)
        colour_groups = {
            'Downloads': tuple(role for role in ROLES if role.startswith('download_')),
            'Surfaces': ('window', 'sidebar', 'panel', 'popup', 'placeholder'),
            'Controls': ('control', 'hover', 'disabled_surface', 'selection', 'accent', 'scrollbar'),
            'Text and accents': ('text', 'secondary_text', 'disabled_text', 'brand', 'error'),
            'Borders and artwork': ('border', 'divider', 'play_surface', 'play_text', 'shadow'),
        }
        for title, roles in colour_groups.items():
            section = self.card(appearance, title)
            grid = QGridLayout()
            grid.setHorizontalSpacing(24)
            grid.setVerticalSpacing(12)
            for index, role in enumerate(roles):
                label, default = ROLES[role]
                button = QPushButton()
                button.setObjectName('colourSwatch')
                button.setFixedWidth(118)
                button.setToolTip('Choose colour for ' + label.lower())
                self.set_colour_button(button, saved_palette[role])
                button.clicked.connect(lambda *_, button=button: self.choose_colour(button))
                self.colour_buttons[role] = button
                field = QWidget()
                field.setObjectName('colourField')
                row = QHBoxLayout(field)
                row.setContentsMargins(0, 0, 0, 0)
                caption = QLabel(label)
                caption.setWordWrap(True)
                row.addWidget(caption, 1)
                row.addWidget(button)
                grid.addWidget(field, index // 2, index % 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            section.addLayout(grid)
        def reset_palette():
            values = base_palette(theme_id=self.theme_source.currentData())
            for role, button in self.colour_buttons.items():
                self.set_colour_button(button, values[role])
        self.theme_source.currentIndexChanged.connect(lambda *_: reset_palette())
        reset = QPushButton('Reset colours to defaults')
        reset.clicked.connect(reset_palette)
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_row.addWidget(reset)
        appearance.addLayout(reset_row)
        appearance.addStretch()
        from .providers import discover_plugins
        self.plugins = discover_plugins()
        plugins_page = QWidget()
        plugins_layout = QVBoxLayout(plugins_page)
        self.plugin_tabs = QTabWidget()
        plugins_layout.addWidget(self.plugin_tabs)
        installed_page = QWidget()
        installed_layout = QVBoxLayout(installed_page)
        installed_layout.setContentsMargins(16, 16, 16, 16)
        installed_layout.setSpacing(12)
        self.installed_status = self.hint('')
        installed_layout.addWidget(self.installed_status)
        self.installed_plugins = QTableWidget(0, 5)
        self.installed_plugins.setHorizontalHeaderLabels(['Plugin', 'Version', 'Type', 'Status', 'Plugin ID'])
        self.installed_plugins.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.configure_plugin_table(self.installed_plugins)
        self.installed_plugins.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.installed_plugins.customContextMenuRequested.connect(self.installed_plugin_context_menu)
        self.installed_plugins.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.installed_plugins.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.refresh_installed_plugins()
        installed_layout.addWidget(self.installed_plugins, 1)
        self.installed_plugin_details = self.operation_log(rows=3)
        self.installed_plugin_details.setPlaceholderText('Select a plugin to see its description, repository and location.')
        installed_layout.addWidget(self.installed_plugin_details)
        def show_plugin_details(row, *unused):
            item = self.installed_plugins.item(row, 0)
            self.installed_plugin_details.setPlainText(item.toolTip() if item else '')
        self.installed_plugins.currentCellChanged.connect(show_plugin_details)
        if self.installed_plugins.rowCount():
            self.installed_plugins.setCurrentCell(0, 0)
        install_plugin = QPushButton('Install / update selected')
        self.update_selected_button = install_plugin
        install_plugin.clicked.connect(self.update_selected_plugins)
        installed_actions = QHBoxLayout()
        installed_actions.addWidget(install_plugin)
        self.delete_plugin_button = QPushButton('Delete selected')
        self.delete_plugin_button.setEnabled(False)
        self.delete_plugin_button.clicked.connect(self.delete_selected_plugins)
        self.installed_plugins.itemSelectionChanged.connect(lambda: self.delete_plugin_button.setEnabled(bool(self.installed_plugins.selectionModel().selectedRows()) and not getattr(self, 'deleting_plugins', False) and not getattr(self, 'installing_plugins', False)))
        self.installed_plugins.itemSelectionChanged.connect(self.update_installed_status)
        self.update_installed_status()
        installed_actions.addWidget(self.delete_plugin_button)
        installed_actions.addStretch()
        installed_layout.addLayout(installed_actions)
        self.plugin_operation_status = self.operation_log()
        installed_layout.addWidget(self.plugin_operation_status)
        self.deleted_plugin_ids = set()
        self.plugin_tabs.addTab(installed_page, 'Installed')
        self.build_available_plugins()
        self.plugin_widgets = {}
        self.plugin_sections = {}
        self.plugin_contributions = []
        self.default_method_group = QButtonGroup(self)
        self.default_method_group.setExclusive(True)
        self.default_method_checks = {}
        self.default_method_owners = {}
        from .providers import installation_methods
        methods = installation_methods(self.plugins)
        default_method = settings.value('installation/defaultMethod', 'Manual', type=str)
        if default_method not in methods:
            default_method = 'Manual'
        self.image_sources = {}
        self.image_filter_defaults = {}
        for kind, kind_title in [('generic', 'General'), ('metadata', 'Metadata'),
                            ('installation', 'Installation')]:
            area = QScrollArea()
            area.setWidgetResizable(True)
            page = QWidget()
            sections = QVBoxLayout(page)
            sections.setSpacing(14)
            heading = QLabel('General settings')
            set_style(heading, 'font-weight: bold;')
            sections.addWidget(heading)
            shared = QWidget()
            form = QFormLayout(shared)
            form.setContentsMargins(0, 0, 0, 0)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
            if kind == 'metadata':
                table = QWidget()
                grid = QGridLayout(table)
                grid.setContentsMargins(0, 0, 0, 0)
                grid.setHorizontalSpacing(12)
                grid.setVerticalSpacing(12)
                form.addRow(self.hint('Default image searches · Used when opening a tab or resetting its filters.'))
                for column, title in enumerate(('Image type', 'Provider', 'Artwork', 'Shape', 'Resolution')):
                    label = QLabel(title)
                    set_style(label, 'font-weight: bold;')
                    grid.addWidget(label, 0, column)
                for row, (key, title) in enumerate([('Icon', 'Icon'), ('CoverImage', 'Cover'),
                                                   ('HeaderImage', 'Header'), ('BackgroundImage', 'Background'), ('Logo', 'Logos')], 1):
                    grid.addWidget(QLabel(title), row, 0, Qt.AlignmentFlag.AlignTop)
                    source = QComboBox()
                    for plugin in self.plugins.values():
                        if plugin.type == 'metadata' and getattr(plugin, 'image_types', ()):
                            source.addItem(plugin.name, plugin.id)
                    fallback = next((plugin.id for plugin in self.plugins.values() if key in getattr(plugin, 'image_types', ())), '')
                    from .image_filters import declared_defaults
                    fallback = declared_defaults(key, self.plugins)[0] or fallback
                    preferred = settings.value(f'images/defaultProvider/{key}', fallback)
                    source.setCurrentIndex(max(0, source.findData(preferred)))
                    source.setEnabled(source.count() > 0)
                    self.image_sources[key] = source
                    grid.addWidget(source, row, 1, Qt.AlignmentFlag.AlignTop)
                    self.image_filter_defaults[key] = {}
                    saved = image_filter_defaults(settings, key, self.plugins)
                    for column, (name, choices) in enumerate(OPTIONS.items(), 2):
                        selector = FilterChecks(name, saved[name])
                        if name == 'resolution':
                            selector.setToolTip('Resolution ranges use the longest edge.')
                        self.image_filter_defaults[key][name] = selector
                        grid.addWidget(selector, row, column, Qt.AlignmentFlag.AlignTop)
                form.addRow(table)
                # Include both tab frames, page margins and the vertical scrollbar.
                required_width = table.minimumSizeHint().width() + 100
                available_width = self.screen().availableGeometry().width() - 40
                self.resize(min(max(self.width(), required_width), available_width), self.height())
            else:
                form.addRow(QLabel('Settings for these plugins are configured individually below.'))
            sections.addWidget(shared)
            from .manual_installation import ManualInstallation
            candidates = list(self.plugins.values()) + ([ManualInstallation()] if kind == 'installation' else [])
            for plugin in sorted((plugin for plugin in candidates
                                  if ('installation' if getattr(plugin, 'settings_group', plugin.type)
                                      in ('installation', 'integration', 'game')
                                      else getattr(plugin, 'settings_group', plugin.type)) == kind),
                                 key=lambda plugin: (0 if plugin.id == 'Manual' else 1,
                                                     plugin.name)):
                widget = plugin.create_settings(page)
                from .providers import IntegrationPlugin
                targets = [plugin] + (plugin.installation_methods() if isinstance(plugin, IntegrationPlugin) else [])
                contributions = []
                for contributor in self.plugins.values():
                    if contributor.id == plugin.id:
                        continue
                    for target in targets:
                        extra = contributor.create_settings_contribution(target, page)
                        if extra is not None:
                            contributions.append((contributor, target, extra))
                add_methods = [target for target in targets if target.type == 'installation']
                if widget is None and not contributions and not add_methods:
                    continue
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                sections.addWidget(separator)
                header = QToolButton()
                header.setText(plugin.name)
                header.setCheckable(True)
                header.setChecked(False)
                header.setArrowType(Qt.ArrowType.RightArrow)
                header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                set_style(header, 'text-align: left; font-weight: bold; padding: 8px;')
                sections.addWidget(header)
                content = QWidget()
                content.hide()
                content_layout = QVBoxLayout(content)
                content_layout.setContentsMargins(0, 0, 0, 0)
                content_layout.setSpacing(14)
                def toggle_section(expanded, header=header, content=content):
                    content.setVisible(expanded)
                    header.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
                header.toggled.connect(toggle_section)
                self.plugin_sections[plugin.id] = (header, content)
                sections.addWidget(content)
                for method in add_methods:
                    checkbox = QCheckBox('Use as default installation method')
                    checkbox.setObjectName('defaultInstallationMethod' + method.id)
                    self.default_method_group.addButton(checkbox)
                    checkbox.setChecked(method.id == default_method)
                    self.default_method_checks[method.id] = checkbox
                    self.default_method_owners[method.id] = plugin.id
                if widget is not None:
                    self.plugin_widgets[plugin.id] = widget
                    content_layout.addWidget(widget)
                for target in targets:
                    target_contributions = [(contributor, extra) for contributor, owner, extra in contributions
                                            if owner is target]
                    checkbox = self.default_method_checks.get(target.id) if target in add_methods else None
                    if target is not plugin and (checkbox is not None or target_contributions):
                        content_layout.addWidget(QLabel(target.name))
                    if checkbox is not None:
                        content_layout.addWidget(checkbox)
                    for contributor, extra in target_contributions:
                        content_layout.addWidget(extra)
                        self.plugin_contributions.append((contributor, target, extra))
            sections.addStretch()
            area.setWidget(page)
            self.plugin_tabs.addTab(area, kind_title)
        self.plugins_directory = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'playlite/plugins'
        folder = QPushButton('Open plugins folder')
        folder.clicked.connect(self.open_plugins_folder)
        plugins_layout.addWidget(folder)
        tabs.addTab(plugins_page, 'Plugins')
        self.setMinimumSize(700, 380)
        if metadata:
            tabs.setCurrentWidget(plugins_page)
            self.plugin_tabs.setCurrentIndex(3)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def operation_log(self, rows=4):
        log = QPlainTextEdit(self)
        log.setReadOnly(True)
        log.setPlaceholderText('Plugin operation results appear here.')
        log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        log.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        set_style(log, 'QPlainTextEdit { background: #1d1e20; color: #999a9d; border: 1px solid #404144; border-radius: 6px; padding: 4px; }')
        log.ensurePolished()
        height = rows * log.fontMetrics().lineSpacing() + 2 * log.document().documentMargin() + 2 * log.frameWidth() + 8
        log.setFixedHeight(int(height))
        return log

    @staticmethod
    def configure_plugin_table(table):
        table.setShowGrid(False)
        table.verticalHeader().hide()
        table.verticalHeader().setDefaultSectionSize(table.fontMetrics().height() + 20)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table.horizontalHeader().setHighlightSections(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        set_style(table, """
            QTableWidget { outline: 0; background: #1d1e20; border: 1px solid #404144; border-radius: 6px; }
            QTableWidget::item { padding: 8px 10px; border-bottom: 1px solid #252628; }
            QHeaderView::section { background: #242527; color: #999a9d; padding: 9px 10px; border: 0; border-bottom: 1px solid #404144; font-weight: normal; }
            QTableCornerButton::section { background: #242527; border: 0; }
            QTableWidget::item:selected:active,
            QTableWidget::item:selected:!active {
                background: #292a2c;
                color: #e9e9e9;
            }
        """)

    def build_available_plugins(self):
        from .plugin_manager import development_checkout
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        self.available_status = self.hint('Refresh to find plugins accessible to this installation.')
        layout.addWidget(self.available_status)
        self.available_plugins = QTableWidget(0, 3)
        self.available_plugins.setHorizontalHeaderLabels(['Plugin', 'Version', 'Description'])
        self.available_plugins.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.configure_plugin_table(self.available_plugins)
        self.available_plugins.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.available_plugins, 1)
        access_details = self.operation_log(rows=3)
        access_details.setPlainText('Repository builds can sign in to access private plugins.\nRelease builds browse anonymously.\nSelect plugins with Ctrl or Shift to install several at once.')
        layout.addWidget(access_details)
        actions = QHBoxLayout()
        refresh = QPushButton('Update list')
        self.available_refresh_button = refresh
        refresh.clicked.connect(self.refresh_available_plugins)
        actions.addWidget(refresh)
        install = QPushButton('Install selected…')
        self.install_selected_button = install
        install.setEnabled(False)
        self.available_plugins.itemSelectionChanged.connect(lambda: install.setEnabled(bool(self.available_plugins.selectionModel().selectedRows()) and not getattr(self, 'installing_plugins', False) and not getattr(self, 'deleting_plugins', False)))
        self.available_plugins.itemSelectionChanged.connect(self.update_available_status)
        install.clicked.connect(self.install_selected_plugins)
        actions.addWidget(install)
        if development_checkout():
            authenticate = QPushButton('Authenticate GitHub…')
            authenticate.clicked.connect(self.authenticate_plugin_github)
            actions.addWidget(authenticate)
            signout = QPushButton('Sign out')
            def logout():
                from .plugin_manager import github_environment
                import shutil
                shutil.rmtree(github_environment()['GH_CONFIG_DIR'], ignore_errors=True)
                self.available_cache.invalidate()
                self.refresh_available_plugins()
            signout.clicked.connect(logout)
            actions.addWidget(signout)
        actions.addStretch()
        layout.addLayout(actions)
        self.available_operation_log = self.operation_log()
        layout.addWidget(self.available_operation_log)
        self.plugin_tabs.addTab(page, 'Available')
        from .plugin_catalogue_cache import catalogue_cache
        self.available_cache = catalogue_cache()
        self.available_cache.changed.connect(self.render_available_plugins)
        self.render_available_plugins()

    def refresh_available_plugins(self):
        self.available_cache.refresh()

    def render_available_plugins(self):
        from PyQt6.QtCore import QVersionNumber
        from .plugin_manager import installed_plugins
        installed = installed_plugins()
        identities = {plugin['id']: plugin for plugin in installed}
        repositories = {plugin[field].casefold(): plugin for plugin in installed
                        for field in ('repository', 'distribution_repository') if plugin.get(field)}
        cache = self.available_cache
        updates = {}
        self.available_plugins.setRowCount(0)
        self.available_refresh_button.setEnabled(not cache.loading)
        for plugin in sorted(cache.plugins, key=lambda plugin: plugin['name'].casefold()):
            current = identities.get(plugin.get('id')) or repositories.get(plugin['repository'].casefold())
            if current:
                latest = QVersionNumber.fromString(plugin['version'].lstrip('v'))[0]
                previous = QVersionNumber.fromString(current['version'].lstrip('v'))[0]
                if latest.isNull() or previous.isNull() or QVersionNumber.compare(latest, previous) <= 0:
                    continue
                updates[current['id']] = plugin
            row = self.available_plugins.rowCount()
            self.available_plugins.insertRow(row)
            for column, key in enumerate(('name', 'version', 'description')):
                item = QTableWidgetItem(plugin[key])
                if current:
                    item.setToolTip(f"Update available: {current['version']} → {plugin['version']}")
                    if column == 0:
                        item.setIcon(QIcon(str(Path(__file__).parent / 'assets/plugin-update.svg')))
                    elif column == 1:
                        item.setText(f"{current['version']} → {plugin['version']}")
                item.setData(Qt.ItemDataRole.UserRole, plugin['repository'])
                self.available_plugins.setItem(row, column, item)
        self.install_selected_button.setText('Install / update selected…')
        for row in range(self.installed_plugins.rowCount()):
            item = self.installed_plugins.item(row, 0)
            current = item.data(Qt.ItemDataRole.UserRole)
            update = updates.get(current['id'])
            item.setIcon(QIcon(str(Path(__file__).parent / 'assets/plugin-update.svg')) if update else QIcon())
            tooltip = item.toolTip().split('\nUpdate available:')[0]
            if update:
                tooltip += f"\nUpdate available: {current['version']} → {update['version']}"
            item.setToolTip(tooltip)
        self.update_available_status()

    def update_installed_status(self):
        self.set_plugin_selection_status(self.installed_plugins, self.installed_status, 'installed')
        if hasattr(self, 'update_selected_button'):
            idle = not getattr(self, 'installing_plugins', False) and not getattr(self, 'deleting_plugins', False)
            selected = bool(self.installed_plugins.selectionModel().selectedRows())
            self.update_selected_button.setEnabled(selected and idle)
            self.delete_plugin_button.setEnabled(selected and idle)

    @staticmethod
    def set_plugin_selection_status(table, label, kind):
        selected = len(table.selectionModel().selectedRows())
        total = table.rowCount()
        label.setText(f'{selected}/{total} plugins selected' if selected > 1 else f'{total} {kind} plugins')

    def update_available_status(self):
        cache = self.available_cache
        if cache.loading:
            self.available_status.setText('Updating available plugins…')
        elif cache.error:
            self.available_status.setText('Could not update list: ' + cache.error)
        elif cache.loaded:
            self.set_plugin_selection_status(self.available_plugins, self.available_status, 'available')
        else:
            self.available_status.setText('Use Update list to load available plugins.')

    def authenticate_plugin_github(self):
        from .plugin_manager import authenticate_github
        dialog = QDialog(self)
        dialog.setWindowTitle('GitHub authentication — repository version')
        layout = QVBoxLayout(dialog)
        layout.addWidget(self.hint('Sign in through your browser to access private repositories available to your account. Credentials stay separate from your normal GitHub CLI login.'))
        browser = QPushButton('Sign in with GitHub in browser')
        layout.addWidget(browser)
        code_label = QLabel()
        code_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(code_label)
        layout.addWidget(self.hint('Or use a personal access token:'))
        token = QLineEdit()
        token.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(token)
        status = self.hint('')
        layout.addWidget(status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(dialog.reject)
        def login():
            from .metadata_dialog import Task
            from PyQt6.QtCore import QThreadPool
            value = token.text()
            token.clear()
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            task = Task(lambda: authenticate_github(value))
            dialog.auth_task = task
            def complete(result):
                dialog.accept()
                self.available_cache.invalidate()
                self.refresh_available_plugins()
            def failed(error):
                status.setText(str(error))
                buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
            task.signals.succeeded.connect(complete)
            task.signals.failed.connect(failed)
            QThreadPool.globalInstance().start(task)
        from PyQt6.QtCore import QProcess, QProcessEnvironment
        from .plugin_manager import github_browser_command, github_environment
        process = QProcess(dialog)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        output = ''
        opened = False
        cancelled = False
        def read_output():
            nonlocal output, opened
            import re
            output += bytes(process.readAllStandardOutput()).decode('utf-8', errors='replace')
            clean = re.sub(r'\x1b\[[0-9;]*m', '', output)
            match = re.search(r'one-time code:\s*([A-Z0-9]{4}-[A-Z0-9]{4})', clean)
            if match and not opened:
                opened = True
                code_label.setText('Enter this code on GitHub: ' + match.group(1))
                status.setText('Waiting for approval in your browser…')
                QDesktopServices.openUrl(QUrl('https://github.com/login/device'))
                process.write(b'\n')
        def browser_finished(exit_code, exit_status):
            if cancelled:
                return
            read_output()
            if exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
                from .plugin_manager import github_environment
                for path in Path(github_environment()['GH_CONFIG_DIR']).glob('*'):
                    if path.is_file():
                        path.chmod(0o600)
                dialog.accept()
                self.available_cache.invalidate()
                self.refresh_available_plugins()
            else:
                status.setText('GitHub sign-in was not completed. Try again or use a token.')
                browser.setEnabled(True)
                buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        def browser_login():
            nonlocal output, opened
            try:
                command = github_browser_command()
            except ValueError as error:
                status.setText(str(error))
                return
            output = ''
            opened = False
            code_label.clear()
            browser.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            status.setText('Requesting a one-time code from GitHub…')
            env = QProcessEnvironment()
            for key, value in github_environment().items():
                env.insert(key, value)
            env.insert('GH_BROWSER', 'true')
            process.setProcessEnvironment(env)
            process.start(command[0], command[1:])
        def stop_login(result):
            nonlocal cancelled
            cancelled = True
            if process.state() != QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(1000)
        process.readyReadStandardOutput.connect(read_output)
        process.finished.connect(browser_finished)
        def process_error(error):
            if not cancelled:
                status.setText('Could not start GitHub sign-in. Check that GitHub CLI is installed.')
                browser.setEnabled(True)
                buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        process.errorOccurred.connect(process_error)
        dialog.finished.connect(stop_login)
        browser.clicked.connect(browser_login)
        buttons.accepted.connect(login)
        layout.addWidget(buttons)
        run_dialog(dialog)

    def update_task(self, function, complete):
        from .metadata_dialog import Task
        from PyQt6.QtCore import QThreadPool
        self.check_update_button.setEnabled(False)
        self.install_update_button.setEnabled(False)
        task = Task(function)
        self.application_update_task = task
        def failed(error):
            self.update_status.setText('Update failed: ' + str(error))
            self.check_update_button.setEnabled(True)
        task.signals.failed.connect(failed)
        task.signals.succeeded.connect(complete)
        QThreadPool.globalInstance().start(task)

    def check_application_update(self):
        from .updater import latest_release
        self.update_status.setText('Checking GitHub releases…')
        def complete(release):
            self.application_release = release
            self.check_update_button.setEnabled(True)
            tag = release['tag_name']
            repo = os.environ.get('PLAYLITE_PROFILE') == 'repo'
            current = tag.lstrip('v') == self.application_version
            message = ' · Update this checkout through Git.' if repo else ' · Already up to date.' if current else ' · Ready to install.'
            self.update_status.setText('Latest release: ' + tag + message)
            self.install_update_button.setEnabled(not repo and not current)
        self.update_task(latest_release, complete)

    def install_application_update(self):
        from .updater import prepare_update, launch_update
        release = getattr(self, 'application_release', None)
        if release is None or os.environ.get('PLAYLITE_PROFILE') == 'repo':
            return
        self.update_status.setText('Downloading and verifying the installer…')
        def complete(directory):
            import shutil
            window = self.parentWidget()
            self.save()
            if self.result() != QDialog.DialogCode.Accepted:
                shutil.rmtree(directory)
                self.check_update_button.setEnabled(True)
                return
            lifecycle = getattr(window, 'lifecycle', None)
            # Updating must close the window rather than hide it in the tray.
            # Keep closeEvent active so downloads can still veto shutdown.
            if lifecycle is not None:
                lifecycle.quitting = True
            try:
                closed = window is not None and window.close()
            finally:
                if lifecycle is not None:
                    lifecycle.quitting = False
            if not closed:
                shutil.rmtree(directory)
                return
            launch_update(directory, release['tag_name'])
            from PyQt6.QtWidgets import QApplication
            if lifecycle is not None:
                lifecycle.quit()
            else:
                QApplication.instance().quit()
        self.update_task(lambda: prepare_update(release), complete)

    def delete_selected_plugins(self):
        from .plugin_manager import delete_plugins
        from .metadata_dialog import Task
        from PyQt6.QtCore import QThreadPool
        if getattr(self, 'deleting_plugins', False) or getattr(self, 'installing_plugins', False):
            return
        identities = [self.installed_plugins.item(index.row(), 4).text()
                      for index in self.installed_plugins.selectionModel().selectedRows()]
        if not identities:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Uninstall plugins')
        layout = QVBoxLayout(dialog)
        label = QLabel('Uninstall selected plugins? External games and libraries are kept.')
        label.setWordWrap(True)
        layout.addWidget(label)
        keep = QCheckBox('Keep user settings for reinstalling')
        keep.setChecked(True)
        layout.addWidget(keep)
        hint = QLabel('Stored credentials and private plugin data are managed separately. Only settings declared by each plugin can be removed.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Uninstall')
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        from .lifecycle import run_dialog
        if run_dialog(dialog) != QDialog.DialogCode.Accepted:
            return
        keep_settings = keep.isChecked()
        from .plugin_lifecycle import prepare_removal
        if not prepare_removal(identities, self, self.plugin_operation_status.appendPlainText):
            return
        self.deleting_plugins = True
        self.update_installed_status()
        self.install_selected_button.setEnabled(False)
        self.delete_plugin_button.setEnabled(False)
        self.plugin_operation_status.clear()
        task = Task(lambda: delete_plugins(identities, task.signals.progress.emit, keep_settings=keep_settings))
        self.batch_delete_task = task
        task.signals.progress.connect(self.plugin_operation_status.appendPlainText)
        def complete(results):
            self.deleting_plugins = False
            self.install_selected_button.setEnabled(bool(self.available_plugins.selectionModel().selectedRows()))
            for identity, plugin, error in results:
                if plugin:
                    self.deleted_plugin_ids.add(identity)
                    for widget in self.plugin_sections.get(identity, ()):
                        widget.hide()
            self.refresh_installed_plugins()
            self.installed_plugin_details.clear()
            if any(plugin for _, plugin, _ in results):
                self.plugin_operation_status.appendPlainText('Restart Playlite to unload deleted plugins.')
        def failed(error):
            self.deleting_plugins = False
            self.install_selected_button.setEnabled(bool(self.available_plugins.selectionModel().selectedRows()))
            self.plugin_operation_status.appendPlainText(str(error))
            self.refresh_installed_plugins()
        task.signals.succeeded.connect(complete)
        task.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(task)

    def update_selected_plugins(self):
        if getattr(self, 'installing_plugins', False) or getattr(self, 'deleting_plugins', False):
            return
        self.plugin_operation_status.clear()
        repositories = []
        for index in self.installed_plugins.selectionModel().selectedRows():
            plugin = self.installed_plugins.item(index.row(), 0).data(Qt.ItemDataRole.UserRole)
            catalogue = next((entry for entry in self.available_cache.plugins
                              if entry.get('id') == plugin['id'] or entry['name'] == plugin['name']), {})
            repository = (plugin.get('distribution_repository') or catalogue.get('repository')
                          or plugin.get('repository'))
            if repository:
                repositories.append(repository)
            else:
                self.plugin_operation_status.appendPlainText(f"No GitHub repository configured for {plugin['name']}.")
        self.start_plugin_install(repositories, self.plugin_operation_status)

    def install_selected_plugins(self):
        repositories = [self.available_plugins.item(index.row(), 0).data(Qt.ItemDataRole.UserRole)
                        for index in self.available_plugins.selectionModel().selectedRows()]
        self.start_plugin_install(repositories, self.available_operation_log)

    def start_plugin_install(self, repositories, log):
        from .plugin_manager import install_plugins
        from .metadata_dialog import Task
        from PyQt6.QtCore import QThreadPool
        if getattr(self, 'installing_plugins', False) or getattr(self, 'deleting_plugins', False) or not repositories:
            return
        self.installing_plugins = True
        from .plugin_manager import installed_plugins
        previously_installed = {plugin['id'] for plugin in installed_plugins()}
        self.update_installed_status()
        self.install_selected_button.setEnabled(False)
        if log is self.available_operation_log:
            log.clear()
        log.appendPlainText(f'Installing {len(repositories)} plugins…')
        task = Task(lambda: install_plugins(repositories, task.signals.progress.emit))
        self.batch_install_task = task
        task.signals.progress.connect(log.appendPlainText)
        def complete(results):
            self.installing_plugins = False
            self.refresh_installed_plugins()
            if any(manifest for _, manifest, _ in results):
                log.appendPlainText('Restart Playlite to load installed plugins.')
                from .plugin_lifecycle import installed_setup
                installed_setup([manifest for _, manifest, _ in results
                                 if manifest and manifest.get('id') not in previously_installed], self, log.appendPlainText)
            self.install_selected_button.setEnabled(bool(self.available_plugins.selectionModel().selectedRows()))
        def failed(error):
            self.installing_plugins = False
            log.appendPlainText(str(error))
            self.update_installed_status()
            self.install_selected_button.setEnabled(bool(self.available_plugins.selectionModel().selectedRows()))
        task.signals.succeeded.connect(complete)
        task.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(task)

    def installed_plugin_context_menu(self, position):
        if getattr(self, 'deleting_plugins', False) or getattr(self, 'installing_plugins', False):
            return
        table = self.installed_plugins
        item = table.itemAt(position)
        if item is None:
            return
        selected_rows = {index.row() for index in table.selectionModel().selectedRows()}
        if item.row() not in selected_rows:
            table.clearSelection()
            table.selectRow(item.row())
        table.setCurrentItem(item, QItemSelectionModel.SelectionFlag.NoUpdate)
        plugins = [table.item(index.row(), 0).data(Qt.ItemDataRole.UserRole)
                   for index in table.selectionModel().selectedRows()]
        identities = [plugin['id'] for plugin in plugins]
        menu = QMenu(table)
        plural = len(plugins) > 1
        if any(not plugin.get('enabled', True) for plugin in plugins):
            menu.addAction('Enable selected' if plural else 'Enable', lambda: self.set_selected_plugins_enabled(identities, True))
        if any(plugin.get('enabled', True) for plugin in plugins):
            menu.addAction('Disable selected' if plural else 'Disable', lambda: self.set_selected_plugins_enabled(identities, False))
        menu.aboutToHide.connect(menu.deleteLater)
        menu.popup(table.viewport().mapToGlobal(position))

    def set_selected_plugins_enabled(self, identities, enabled):
        from .plugin_manager import set_plugin_enabled
        messages = []
        for identity in identities:
            try:
                plugin = set_plugin_enabled(identity, enabled)
                messages.append(f'{plugin["name"]}: {"Enabled" if enabled else "Disabled"}.')
            except (ValueError, OSError) as error:
                messages.append(f'{identity}: {error}')
        self.refresh_installed_plugins()
        for row in range(self.installed_plugins.rowCount()):
            if self.installed_plugins.item(row, 4).text() in identities:
                self.installed_plugins.selectionModel().select(self.installed_plugins.model().index(row, 0),
                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.plugin_operation_status.setPlainText('\n'.join(messages + ['Restart Playlite to apply plugin changes.']))

    def refresh_installed_plugins(self):
        from .plugin_manager import installed_plugins
        self.installed_plugins.setRowCount(0)
        for plugin in sorted(installed_plugins(), key=lambda plugin: plugin.get('name', '').casefold()):
            row = self.installed_plugins.rowCount()
            self.installed_plugins.insertRow(row)
            for column, value in enumerate((plugin['name'], plugin['version'], plugin.get('type', 'metadata').capitalize(),
                                             'Enabled' if plugin.get('enabled', True) else 'Disabled', plugin['id'])):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, plugin)
                item.setToolTip('\n'.join(str(value) for value in
                    (plugin.get('description', ''), plugin.get('repository', ''), plugin.get('manifest_path', '')) if value))
                self.installed_plugins.setItem(row, column, item)
        self.update_installed_status()
        if hasattr(self, 'available_cache'):
            self.render_available_plugins()

    def install_plugin(self, checked=False, selected_repository=None):
        if getattr(self, 'deleting_plugins', False) or getattr(self, 'installing_plugins', False):
            self.plugin_operation_status.appendPlainText('Wait for the current plugin operation to finish.')
            return
        from .plugin_manager import install_github
        from .metadata_dialog import Task
        from PyQt6.QtCore import QThreadPool
        dialog = QDialog(self)
        dialog.setWindowTitle('Install plugin from GitHub')
        layout = QVBoxLayout(dialog)
        layout.addWidget(self.hint('Choose a plugin repository. Private repositories require authentication in the Available tab.'))
        repository = QComboBox()
        repository.setEditable(True)
        from .plugin_manager import installed_plugins
        installed = installed_plugins()
        available = self.available_cache.plugins
        current = self.installed_plugins.item(self.installed_plugins.currentRow(), 0)
        current_name = current.text() if current else ''
        preferred = selected_repository or next((plugin['repository'] for plugin in available
                                                 if plugin['name'] == current_name), '')
        if not preferred:
            preferred = next((plugin.get('repository', '') for plugin in installed
                              if plugin['name'] == current_name), '')
        addresses = [preferred] if preferred else []
        addresses.extend(plugin['repository'] for plugin in sorted(available, key=lambda plugin: plugin['name'].casefold()))
        addresses.extend(plugin.get('repository', '') for plugin in installed)
        for address in dict.fromkeys(addresses):
            if address:
                repository.addItem(address)
        repository.setMinimumContentsLength(42)
        repository.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        repository.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        repository.lineEdit().setPlaceholderText('owner/repository or GitHub repository URL')
        layout.addWidget(repository)
        status = QLabel()
        status.setWordWrap(True)
        layout.addWidget(status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        install = buttons.addButton('Install / update', QDialogButtonBox.ButtonRole.ActionRole)
        install.setEnabled(bool(repository.currentText().strip()))
        repository.editTextChanged.connect(lambda text: install.setEnabled(bool(text.strip())))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        def start():
            install.setEnabled(False)
            repository.setEnabled(False)
            status.setText('Downloading and installing plugin…')
            address = repository.currentText()
            task = Task(lambda: install_github(address))
            dialog.install_task = task
            def complete(manifest):
                self.refresh_installed_plugins()
                status.setText(f"Installed {manifest['name']} {manifest['version']}. Restart Playlite to load it.")
                install.setEnabled(True)
                repository.setEnabled(True)
            def failed(error):
                status.setText('Installation failed. Check repository access and authentication. ' + str(error))
                install.setEnabled(True)
                repository.setEnabled(True)
            task.signals.succeeded.connect(complete)
            task.signals.failed.connect(failed)
            QThreadPool.globalInstance().start(task)
        install.clicked.connect(start)
        dialog.resize(640, dialog.sizeHint().height())
        run_dialog(dialog)

    @staticmethod
    def hint(text, name='settingsHint'):
        label = QLabel(text)
        label.setObjectName(name)
        label.setWordWrap(True)
        return label

    @staticmethod
    def card(parent_layout, title):
        frame = QFrame()
        frame.setObjectName('settingsCard')
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)
        heading = QLabel(title)
        heading.setObjectName('settingsHeading')
        layout.addWidget(heading)
        parent_layout.addWidget(frame)
        return layout

    def open_plugins_folder(self):
        self.plugins_directory.mkdir(parents=True, exist_ok=True)
        open_folder(self.plugins_directory)

    def set_colour_button(self, button, value):
        color = QColor(value)
        button.setProperty('selected_colour', color.name())
        button.setText(color.name())
        swatch = QPixmap(24, 24)
        swatch.fill(color)
        button.setIcon(QIcon(swatch))

    def choose_colour(self, button):
        dialog = QColorDialog(QColor(button.property('selected_colour')), self)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if run_dialog(dialog) == QDialog.DialogCode.Accepted:
            self.set_colour_button(button, dialog.selectedColor().name())

    def edit_link_names(self):
        dialog = LinkNamesDialog(self.link_names, self)
        if run_dialog(dialog) == QDialog.DialogCode.Accepted:
            self.link_names = dialog.names

    def save(self):
        prefix_folder = self.default_prefix_folder.text().strip()
        if prefix_folder and not Path(prefix_folder).expanduser().is_absolute():
            self.error.setText('Default Wine prefix parent folder must be an absolute path.')
            return
        install_folder=self.default_install_folder.text().strip()
        if install_folder and not Path(install_folder).expanduser().is_absolute():
            self.error.setText('Choose an absolute default installation folder.');return
        if getattr(self, 'installing_plugins', False) or getattr(self, 'deleting_plugins', False):
            self.error.setText('Wait for the plugin operation to finish before saving settings.')
            return
        try:
            for plugin_id, plugin in self.plugins.items():
                if plugin_id in self.plugin_widgets and plugin_id not in self.deleted_plugin_ids:
                    plugin.save_settings(self.plugin_widgets[plugin_id])
            for contributor, target, widget in self.plugin_contributions:
                if contributor.id not in self.deleted_plugin_ids and target.id not in self.deleted_plugin_ids:
                    contributor.save_settings_contribution(target, widget)
        except (ValueError, OSError) as error:
            self.error.setText(str(error))
            return
        default_method = next((identity for identity, checkbox in self.default_method_checks.items()
                               if checkbox.isChecked() and self.default_method_owners[identity] not in self.deleted_plugin_ids), 'Manual')
        self.settings.setValue('installation/defaultMethod', default_method)
        self.settings.setValue('installation/defaultPrefixFolder', str(Path(prefix_folder).expanduser()) if prefix_folder else '')
        self.settings.setValue('installation/defaultFolder',str(Path(install_folder).expanduser()) if install_folder else '')
        self.settings.setValue('descriptions/hideRepeatedSentences', self.hide_description_overlap.isChecked())
        self.settings.setValue('app/defaultView', self.default_view.currentData())
        self.settings.setValue('links/friendlyNames', json.dumps(self.link_names))
        self.settings.setValue('app/resetSortingFilters', self.reset_on_launch.isChecked())
        self.settings.setValue('app/closeToTray', self.close_to_tray.isChecked())
        self.settings.setValue('appearance/backgroundBlur', self.background_blur.value())
        for key, slider in self.panel_transparency.items():
            self.settings.setValue(f'appearance/{key}', slider.value())
        self.settings.setValue('appearance/theme', self.theme_source.currentData())
        for role, button in self.colour_buttons.items():
            self.settings.setValue('appearance/palette/' + role, button.property('selected_colour'))
        self.settings.remove('appearance/colours')
        for key, filters in self.image_filter_defaults.items():
            for name, selector in filters.items():
                self.settings.setValue(f'images/defaultFilters/{key}/{name}/selected', selector.values())
        for key, source in self.image_sources.items():
            if source.currentData() is not None:
                self.settings.setValue(f'images/defaultProvider/{key}', source.currentData())
        self.settings.sync()
        apply_theme(self.settings)
        self.accept()
