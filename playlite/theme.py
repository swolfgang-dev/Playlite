"""Saved UI colours, shared by stylesheets, painted widgets and SVG controls."""
import hashlib
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from PyQt6.QtGui import QColor, QPalette
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
    'download_card': ('Download cards', '#292b2e'),
    'download_button': ('Download buttons', '#3b4654'),
    'download_button_border': ('Download button borders', '#566477'),
    'download_button_hover': ('Download button hover', '#4b5b70'),
    'download_button_pressed': ('Download button pressed', '#303c4b'),
    'download_button_disabled': ('Disabled download buttons', '#30343a'),
    'download_button_disabled_text': ('Disabled download button text', '#7f8791'),
}
# Built-in themes use the same role contract as theme plugins.
BUILTIN_THEMES = {
    # Adapted for Playlite from https://catppuccin.com/palette/ (Mocha).
    'mocha': ('Mocha', {
        'window': '#181825', 'sidebar': '#11111b', 'panel': '#1e1e2e',
        'popup': '#313244', 'control': '#313244', 'hover': '#45475a',
        'disabled_surface': '#1e1e2e', 'selection': '#45475a',
        'accent': '#b4befe', 'border': '#585b70', 'divider': '#313244',
        'scrollbar': '#585b70', 'text': '#cdd6f4',
        'secondary_text': '#bac2de', 'disabled_text': '#7f849c',
        'placeholder': '#313244', 'brand': '#f5c2e7', 'error': '#f38ba8',
        'play_surface': '#b4befe', 'play_text': '#11111b', 'shadow': '#11111b',
        'download_card': '#1e1e2e', 'download_button': '#313244',
        'download_button_border': '#585b70', 'download_button_hover': '#45475a',
        'download_button_pressed': '#181825', 'download_button_disabled': '#1e1e2e',
        'download_button_disabled_text': '#7f849c',
    }),
    # Adapted for Playlite from https://www.nordtheme.com/.
    'nord': ('Nord', {
        'window': '#2e3440', 'sidebar': '#2e3440', 'panel': '#3b4252',
        'popup': '#434c5e', 'control': '#434c5e', 'hover': '#4c566a',
        'disabled_surface': '#3b4252', 'selection': '#4c566a',
        'accent': '#88c0d0', 'border': '#4c566a', 'divider': '#434c5e',
        'scrollbar': '#81a1c1', 'text': '#eceff4',
        'secondary_text': '#d8dee9', 'disabled_text': '#81a1c1',
        'placeholder': '#434c5e', 'brand': '#b48ead', 'error': '#bf616a',
        'play_surface': '#88c0d0', 'play_text': '#2e3440', 'shadow': '#2e3440',
        'download_card': '#3b4252', 'download_button': '#434c5e',
        'download_button_border': '#81a1c1', 'download_button_hover': '#4c566a',
        'download_button_pressed': '#2e3440', 'download_button_disabled': '#3b4252',
        'download_button_disabled_text': '#81a1c1',
    }),
    'blue-grey': ('Blue Grey', {
        'window': '#293440', 'sidebar': '#253341', 'panel': '#354351',
        'popup': '#3c4b5b', 'control': '#46586a', 'hover': '#58718a',
        'disabled_surface': '#394653', 'selection': '#355c7d',
        'accent': '#78c4ff', 'border': '#617589', 'divider': '#485b6d',
        'scrollbar': '#7891a8', 'text': '#f3f7fb',
        'secondary_text': '#c2ceda', 'disabled_text': '#97a8b8',
        'placeholder': '#3b4d5f', 'brand': '#9acfff', 'error': '#ffc1bd',
        'play_surface': '#b5ddff', 'play_text': '#173650', 'shadow': '#152433',
        'download_card': '#3b4c5e', 'download_button': '#476a8c',
        'download_button_border': '#7ea6ca', 'download_button_hover': '#557fa7',
        'download_button_pressed': '#365671', 'download_button_disabled': '#405061',
        'download_button_disabled_text': '#a4b5c5',
    }),
}
# Compatibility for existing styles, painted widgets, SVGs and saved palettes.
ALIASES = {default: role for role, (_, default) in ROLES.items()}
ALIASES.update({
    '#777777': 'disabled_text',
    '#202123': 'panel', '#45474b': 'border',
    '#151617': 'sidebar', '#171819': 'sidebar', '#222325': 'hover', '#343638': 'selection', '#3b3d41': 'selection',
    '#48566c': 'selection', '#363638': 'control', '#62646a': 'border',
    '#879bb7': 'accent', '#98caff': 'accent', '#747b83': 'disabled_text',
    '#85868a': 'secondary_text', '#b3b4b7': 'text', '#b8b8b8': 'border',
    '#cccccc': 'divider', '#ffffff': 'text', '#68696c': 'secondary_text',
})
COLOURS = {default: ROLES[role][0] for default, role in ALIASES.items()}
for _, supplied in BUILTIN_THEMES.values():
    COLOURS.update({value: ROLES[role][0] for role, value in supplied.items()})
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
    if selected in BUILTIN_THEMES:
        result.update(BUILTIN_THEMES[selected][1])
        return result
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
    if source.name not in ('chevron-down.svg', 'chevron-down-dark.svg', 'checkbox-check.svg', 'checkbox-check-disabled.svg', 'checkbox-partial.svg', 'game-placeholder.svg', 'cover-placeholder.svg'):
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
    accent = QColor(colour('accent'))
    result = result.replace('@accent_text', '#151515' if accent.lightnessF() > .55 else '#ffffff')
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
    native = QPalette()
    roles = {
        'Window': 'window', 'WindowText': 'text', 'Base': 'window',
        'AlternateBase': 'panel', 'Text': 'text', 'Button': 'control',
        'ButtonText': 'text', 'Highlight': 'accent', 'HighlightedText': 'text',
        'ToolTipBase': 'popup', 'ToolTipText': 'text', 'PlaceholderText': 'secondary_text',
        'Link': 'accent', 'LinkVisited': 'secondary_text',
    }
    for name, role in roles.items():
        native.setColor(getattr(QPalette.ColorRole, name), QColor(colour(role)))
    for name in ('WindowText', 'Text', 'ButtonText', 'HighlightedText'):
        native.setColor(QPalette.ColorGroup.Disabled, getattr(QPalette.ColorRole, name), QColor(colour('disabled_text')))
    app.setPalette(native)
    from PyQt6.QtWidgets import QDialogButtonBox
    for box in app.allWidgets():
        if isinstance(box, QDialogButtonBox):
            for button in box.buttons():
                standard = box.standardButton(button)
                name = 'SP_Dialog' + standard.name + 'Button'
                from PyQt6.QtWidgets import QStyle
                icon = getattr(QStyle.StandardPixmap, name, None)
                if icon is not None:
                    button.setIcon(app.style().standardIcon(icon))
    for widget in [app, *app.allWidgets()]:
        template = widget.property('_theme_stylesheet')
        if isinstance(template, str):
            widget.setStyleSheet(stylesheet(template))
        if widget is not app:
            widget.update()
