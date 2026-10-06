"""Shared checkbox filters and migration of saved image search defaults."""
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QPushButton, QMenu, QWidgetAction
from .theme import set_style
from .ui_style import CHEVRON

OPTIONS = {
    'artwork': [('Icons', 'Icon'), ('Logos', 'Logo'), ('Covers', 'CoverImage'),
                ('Headers', 'HeaderImage'), ('Backgrounds', 'BackgroundImage')],
    'shape': [('Square', 'square'), ('Portrait', 'portrait'),
              ('Landscape', 'landscape'), ('Wide (2:1 or wider)', 'wide'),
              ('Exactly 2:3', '2:3'), ('Exactly 16:9', '16:9'), ('Exactly 96:31', '96:31')],
    'resolution': [('Up to 256 px', 0), ('256–512 px', 256), ('512–1024 px', 512),
                   ('1024–1920 px', 1024), ('1920 px and above', 1920)],
}


RESOLUTION_RANGES = {0: (0, 256), 256: (256, 512), 512: (512, 1024),
                     1024: (1024, 1920), 1920: (1920, float('inf'))}


def matches_shape(width, height, selected):
    if len(selected) == len(OPTIONS['shape']):
        return True
    if width <= 0 or height <= 0:
        return False
    ratio = width / height
    shape = ('square' if 0.95 <= ratio <= 1.05 else 'portrait' if ratio < 0.95
             else 'wide' if ratio >= 2 else 'landscape')
    return shape in selected or any(
        value in selected and width * denominator == height * numerator
        for value, numerator, denominator in [('2:3', 2, 3), ('16:9', 16, 9), ('96:31', 96, 31)])


def matches_resolution(edge, selected):
    return any(RESOLUTION_RANGES[value][0] <= edge <= RESOLUTION_RANGES[value][1]
               for value in selected if value in RESOLUTION_RANGES)


class FilterChecks(QPushButton):
    changed = pyqtSignal()

    def __init__(self, name, selected, parent=None):
        super().__init__(parent)
        self.name = name
        self.boxes = {}
        self.setObjectName('filterDropdown')
        self.setMinimumWidth(155)
        self.setMaximumWidth(230)
        set_style(self, f"""
QPushButton#filterDropdown {{ background: #2c2d2f; text-align: left; padding: 8px 30px 8px 10px; }}
QPushButton#filterDropdown:hover {{ background: #48494b; }}
QPushButton#filterDropdown::menu-indicator {{ image: url("{CHEVRON}");
    subcontrol-origin: padding; subcontrol-position: right center; width: 14px; height: 14px; right: 8px; }}
""")
        menu = QMenu(self)
        self.setMenu(menu)
        panel = QWidget()
        panel.setObjectName('filterOptions')
        set_style(panel, 'QWidget#filterOptions { background: #242527; } QCheckBox { background: transparent; }')
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        self.all = QCheckBox('All')
        layout.addWidget(self.all)
        for title, value in OPTIONS[name]:
            box = QCheckBox(title)
            self.boxes[value] = box
            layout.addWidget(box)
            box.toggled.connect(self.update_all)
        action = QWidgetAction(menu)
        action.setDefaultWidget(panel)
        menu.addAction(action)
        self.all.clicked.connect(lambda checked: self.set_values(list(self.boxes) if checked else []))
        self.set_values(selected)

    def values(self):
        return [value for value, box in self.boxes.items() if box.isChecked()]

    def set_values(self, values):
        for value, box in self.boxes.items():
            box.blockSignals(True)
            box.setChecked(value in values)
            box.blockSignals(False)
        self.update_all()

    def update_all(self, *_):
        self.all.setChecked(all(box.isChecked() for box in self.boxes.values()))
        selected = self.values()
        summary = ('All' if len(selected) == len(self.boxes) else 'None' if not selected
                   else next(title for title, value in OPTIONS[self.name] if value == selected[0])
                   if len(selected) == 1 else f'{len(selected)} selected')
        self.setText(summary)
        self.changed.emit()


def declared_defaults(image_type, plugins=None):
    if plugins is None:
        from .providers import discover_plugins
        plugins = discover_plugins()
    for plugin in plugins.values():
        declarations = getattr(plugin, 'image_defaults', {})
        if not isinstance(declarations, dict):
            continue
        declaration = declarations.get(image_type)
        if isinstance(declaration, dict) and image_type in getattr(plugin, 'image_types', ()):
            return plugin.id, declaration
    return '', {}


def apply_install_defaults(manifest, data):
    """Seed plugin-declared defaults without replacing saved user preferences."""
    from PyQt6.QtCore import QSettings
    settings = QSettings(str(data / 'ui.ini'), QSettings.Format.IniFormat)
    for key, declaration in manifest.get('image_defaults', {}).items():
        if key not in dict(OPTIONS['artwork']).values():
            continue
        path = f'images/defaultProvider/{key}'
        if not settings.contains(path):
            settings.setValue(path, manifest['id'])
        for name, values in declaration.items():
            if name not in OPTIONS or not isinstance(values, list):
                continue
            path = f'images/defaultFilters/{key}/{name}'
            if not settings.contains(path) and not settings.contains(path + '/selected'):
                settings.setValue(path + '/selected', [value for _, value in OPTIONS[name] if value in values])
    settings.sync()


def defaults(settings, image_type, plugins=None):
    values = {name: [value for _, value in choices] for name, choices in OPTIONS.items()}
    values['artwork'] = [image_type]
    _, declaration = declared_defaults(image_type, plugins)
    for name, selected in declaration.items():
        if name in OPTIONS:
            values[name] = [value for _, value in OPTIONS[name] if value in selected]
    if settings:
        for name, fallback in values.items():
            path = f'images/defaultFilters/{image_type}/{name}'
            if settings.contains(path + '/selected'):
                saved = settings.value(path + '/selected', [], type=list)
                values[name] = [value for _, value in OPTIONS[name] if str(value) in {str(item) for item in saved}]
            elif settings.contains(path):
                old = settings.value(path)
                if old in ('all', 'any'):
                    values[name] = [value for _, value in OPTIONS[name]]
                elif name == 'resolution':
                    try:
                        values[name] = [value for _, value in OPTIONS[name] if value >= int(old)]
                    except (ValueError, TypeError):
                        pass
                elif old not in ('all', 'any') and old in dict(OPTIONS[name]).values():
                    values[name] = [old] + (['wide'] if old == 'landscape' else [])
    return values
