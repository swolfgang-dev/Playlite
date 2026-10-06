"""Predictable native controls and readable standard button symbols."""
from pathlib import Path
from PyQt6.QtGui import QColor, QIcon, QPainter
from PyQt6.QtWidgets import QProxyStyle, QStyle, QStyleFactory
from .theme import colour


class ApplicationStyle(QProxyStyle):
    def __init__(self):
        super().__init__(QStyleFactory.create('Fusion'))

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_DialogButtonBox_ButtonsHaveIcons:
            return 1
        return super().styleHint(hint, option, widget, returnData)

    def standardIcon(self, standard_icon, option=None, widget=None):
        source = (QIcon(str(Path(__file__).parent / 'assets/dialog-save.svg'))
                  if standard_icon == QStyle.StandardPixmap.SP_DialogSaveButton
                  else super().standardIcon(standard_icon, option, widget))
        if not standard_icon.name.startswith('SP_Dialog'):
            return source
        result = QIcon()
        for size in (16, 24, 32, 48, 64):
            for mode, role in ((QIcon.Mode.Normal, 'text'), (QIcon.Mode.Disabled, 'disabled_text')):
                pixmap = source.pixmap(size, size)
                if pixmap.isNull():
                    continue
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor(colour(role)))
                painter.end()
                result.addPixmap(pixmap, mode)
        return result


def configure(app):
    app.setStyle(ApplicationStyle())
