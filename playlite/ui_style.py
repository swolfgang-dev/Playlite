from pathlib import Path

CHEVRON = (Path(__file__).parent / 'assets' / 'chevron-down.svg').as_posix()
DROPDOWN_STYLE = f"""
QComboBox {{ background: #2c2d2f; border: 0; border-radius: 8px; padding: 7px 30px 7px 10px; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right;
    width: 24px; border: 0; background: transparent;
    border-top-right-radius: 8px; border-bottom-right-radius: 8px; }}
QComboBox::down-arrow {{ image: url("{CHEVRON}"); width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{ background: #2c2d2f; selection-background-color: #48494b; }}
"""


# A clickable path that preserves the useful filename/folder at narrow widths.
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QPushButton, QSizePolicy


class PathButton(QPushButton):
    def __init__(self, path, parent=None):
        super().__init__(path, parent)
        self.path = path
        self.setToolTip(path)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self.fontMetrics().elidedText(self.path, Qt.TextElideMode.ElideLeft,
                                                 max(0, self.width() - 4)))

    def sizeHint(self):
        return QSize(0, self.fontMetrics().height())
