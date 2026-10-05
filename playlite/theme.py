"""Saved UI colours, shared by stylesheets, painted widgets and SVG controls."""
import hashlib
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication


# Stable names are the palette contract for themes and user overrides.
ROLES = {
    'window': ('Window background', '#101112'),
    'sidebar': ('Library side panel', '#141516'),
    'panel': ('Game and settings panels', '#1d1e20'),
    'popup': ('Menus and tooltips', '#242527'),
    'control': ('Inputs, dropdowns and buttons', '#2c2d2f'),
    'hover': ('Hover and checked controls', '#48494b'),
    'disabled_surface': ('Disabled controls', '#292a2b'),
    'selection': ('Selected rows, tiles and text', '#292a2c'),
    'accent': ('Focus, sliders, links and chosen images', '#2196f3'),
    'border': ('Panel, menu and tooltip borders', '#404144'),
    'divider': ('Dividers', '#252628'),
    'scrollbar': ('Scrollbar handles', '#414246'),
    'text': ('Primary text and icons', '#e9e9e9'),
    'secondary_text': ('Secondary and helper text', '#999a9d'),
    'disabled_text': ('Disabled text and placeholder icons', '#777'),
    'placeholder': ('Artwork placeholders', '#292a2d'),
    'brand': ('Brand accent', '#dc69a1'),
    'error': ('Errors', '#ffaaaa'),
    'play_surface': ('Play button background', '#f0f0f0'),
    'play_text': ('Play button text', '#151515'),
    'shadow': ('Artwork shadow', '#000000'),
}
# Compatibility for existing styles, painted widgets, SVGs and saved palettes.
ALIASES = {default: role for role, (_, default) in ROLES.items()}
ALIASES.update({
    '#151617': 'sidebar', '#171819': 'sidebar', '#222325': 'hover', '#343638': 'selection', '#3b3d41': 'selection',
    '#48566c': 'selection', '#363638': 'control', '#62646a': 'border',
    '#879bb7': 'accent', '#98caff': 'accent', '#747b83': 'disabled_text',
    '#85868a': 'secondary_text', '#b3b4b7': 'text', '#b8b8b8': 'border',
    '#cccccc': 'divider', '#ffffff': 'text', '#68696c': 'secondary_text',
})
COLOURS = {default: ROLES[role][0] for default, role in ALIASES.items()}
_values = {}
_assets = TemporaryDirectory(prefix='playlite-theme-')


def colour(default):
    role = ALIASES.get(default.lower(), default)
    return _values.get(role, ROLES[role][1] if role in ROLES else default)


def rgba(default, alpha):
    value = QColor(colour(default))
    return f'rgba({value.red()}, {value.green()}, {value.blue()}, {alpha})'


def base_palette(settings=None, theme_id=None):
    result = {role: default for role, (_, default) in ROLES.items()}
    selected = theme_id if theme_id is not None else settings.value('appearance/theme', '') if settings else ''
    if selected:
        from .providers import discover_plugins, ThemePlugin
        plugin = discover_plugins().get(selected)
        if isinstance(plugin, ThemePlugin):
            supplied = plugin.palette()
            if isinstance(supplied, dict):
                for role, value in supplied.items():
                    if role in ROLES and isinstance(value, str) and QColor(value).isValid():
                        result[role] = QColor(value).name()
    return result


def palette(settings):
    result = base_palette(settings)
    for role in ROLES:
        saved = settings.value('appearance/palette/' + role)
        if isinstance(saved, str) and QColor(saved).isValid():
            result[role] = QColor(saved).name()
            continue
        # Prefer a canonical custom colour, then a customised former alias.
        aliases = [default for default, target in ALIASES.items() if target == role]
        for default in aliases:
            value = settings.value('appearance/colours/' + default[1:])
            if isinstance(value, str) and QColor(value).isValid() and QColor(value) != QColor(default):
                result[role] = QColor(value).name()
                break
    return result


def load(settings):
    global _values
    _values = palette(settings)


def themed_asset(filename):
    source = Path(filename)
    if source.name not in ('chevron-down.svg', 'chevron-down-dark.svg', 'game-placeholder.svg', 'cover-placeholder.svg'):
        return str(filename)
    content = re.sub(r'#[0-9a-fA-F]{6}\b', lambda match: colour(match[0]), source.read_text())
    target = Path(_assets.name) / (hashlib.sha256(content.encode()).hexdigest() + '.svg')
    if not target.exists():
        target.write_text(content)
    return str(target)


def stylesheet(template):
    result = re.sub(r'#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b', lambda match: colour(match[0]), template)
    result = re.sub(r'(?<=background: )white\b', colour('#ffffff'), result)
    for default in ('#141516', '#1d1e20'):
        rgb = QColor(default)
        pattern = rf'rgba\({rgb.red()},\s*{rgb.green()},\s*{rgb.blue()},\s*(\d+)\)'
        result = re.sub(pattern, lambda match: rgba(default, int(match[1])), result)
    return re.sub(r'url\(["\']?([^()"\']+\.svg)["\']?\)',
                  lambda match: f'url("{themed_asset(match[1])}")' if Path(match[1]).is_file() else match[0], result)


def set_style(widget, template):
    widget.setProperty('_theme_stylesheet', template)
    widget.setStyleSheet(stylesheet(template))


def apply(settings):
    load(settings)
    app = QApplication.instance()
    if app is None:
        return
    for widget in [app, *app.allWidgets()]:
        template = widget.property('_theme_stylesheet')
        if isinstance(template, str):
            widget.setStyleSheet(stylesheet(template))
        if widget is not app:
            widget.update()
