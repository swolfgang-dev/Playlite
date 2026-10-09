"""Checkbox dropdowns for library filters; an empty selection means all values."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QMenu, QPushButton, QScrollArea,
                             QSizePolicy, QVBoxLayout, QWidget, QWidgetAction)
from .theme import set_style
from .ui_style import CHEVRON


class FilterChoice(QCheckBox):
    def hitButton(self, position):
        return self.rect().contains(position)


class LibraryFilter(QPushButton):
    changed = pyqtSignal()

    def __init__(self, title, options, selected=None, parent=None):
        super().__init__(parent)
        self.title = title
        self.setObjectName('libraryFilterDropdown')
        self.setAccessibleName(title)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        set_style(self, f'''
QPushButton#libraryFilterDropdown {{ background: #2c2d2f; text-align: left; padding: 7px 30px 7px 10px; }}
QPushButton#libraryFilterDropdown:hover {{ background: #48494b; }}
QPushButton#libraryFilterDropdown::menu-indicator {{ image: url("{CHEVRON}");
    subcontrol-origin: padding; subcontrol-position: right center; width: 14px; height: 14px; right: 8px; }}
''')
        self.setMenu(QMenu(self))
        self.set_options(options, selected)

    def values(self):
        return [value for value, box in self.boxes.items() if box.isChecked()]

    def set_values(self, selected):
        # Older settings stored a single string per filter.
        selected = selected if isinstance(selected, list) else [selected] if selected else []
        for value, box in self.boxes.items():
            box.blockSignals(True)
            box.setChecked(value in selected)
            box.blockSignals(False)
        self.update_summary()

    def set_options(self, options, selected=None):
        self.menu().clear()
        self.options = list(options)
        self.boxes = {}
        panel = QWidget()
        panel.setObjectName('libraryFilterOptions')
        set_style(panel, 'QWidget#libraryFilterOptions { background: #242527; } QCheckBox { background: transparent; }')
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        self.all = FilterChoice(f'All {self.title.lower()}')
        self.all.clicked.connect(lambda: self.set_values([]))
        layout.addWidget(self.all)
        for label, value in self.options:
            box = FilterChoice(label)
            box.setAccessibleName(f'{self.title}: {label}')
            self.boxes[value] = box
            layout.addWidget(box)
            box.toggled.connect(self.update_summary)
        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(max(240, panel.sizeHint().width() + 24))
        height = min(420, max(120, self.screen().availableGeometry().height() // 2))
        scroll.setFixedHeight(min(height, panel.sizeHint().height() + 2))
        action = QWidgetAction(self.menu())
        action.setDefaultWidget(scroll)
        self.menu().addAction(action)
        self.set_values(selected)

    def update_summary(self, *_):
        selected = self.values()
        self.all.setChecked(not selected)
        labels = [label for label, value in self.options if value in selected]
        self.setText(f'All {self.title.lower()}' if not labels else
                     f'{self.title}: None' if selected == [None] else
                     labels[0] if len(labels) == 1 else f'{self.title}: {len(labels)} selected')
        self.setToolTip(f'{self.title}: ' + (', '.join(labels) if labels else 'All'))
        self.changed.emit()
