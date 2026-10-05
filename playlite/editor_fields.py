from .lifecycle import ask_text
"""Compact list fields and editable, ordered links for the metadata page."""
from .lifecycle import run_dialog
import csv
import io
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog,
                             QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget, QMenu)


class ListField(QWidget):
    def __init__(self, values, title, parent=None):
        super().__init__(parent)
        self.title = title
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.input = QLineEdit()
        self.input.setFixedHeight(40)
        self.input.setPlaceholderText('No values')
        self.input.setToolTip('Comma-separated values; quote values that contain commas. Use ▾ to edit one per line.')
        layout.addWidget(self.input, 1)
        edit = QPushButton('▾')
        edit.setObjectName('compact')
        edit.setFixedSize(30, 40)
        edit.setToolTip(f'Edit {title.lower()}')
        edit.clicked.connect(self.edit_values)
        layout.addWidget(edit)
        add = QPushButton('+')
        add.setObjectName('compact')
        add.setFixedSize(30, 40)
        add.setToolTip(f'Add {title.lower()}')
        add.clicked.connect(self.add_value)
        layout.addWidget(add)
        self.setPlainText('\n'.join(values))

    def toPlainText(self):
        values = next(csv.reader([self.input.text()], skipinitialspace=True), [])
        return '\n'.join(value.strip() for value in values if value.strip())

    def setPlainText(self, text):
        buffer = io.StringIO()
        csv.writer(buffer, lineterminator='').writerow(text.splitlines())
        self.input.setText(buffer.getvalue())

    def edit_values(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.title)
        dialog.resize(420, 320)
        layout = QVBoxLayout(dialog)
        field = QPlainTextEdit(self.toPlainText())
        field.setPlaceholderText('One value per line')
        layout.addWidget(field)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if run_dialog(dialog) == QDialog.DialogCode.Accepted:
            self.setPlainText(field.toPlainText())

    def add_value(self):
        value, accepted = ask_text(self, self.title, 'New value')
        if accepted and value.strip():
            self.setPlainText('\n'.join(filter(None, [self.toPlainText(), value.strip()])))


class CompletionField(ListField):
    def __init__(self, values, parent=None):
        super().__init__(values, 'Completion status', parent)
        self.input.setReadOnly(True)
        self.input.setPlaceholderText('Select completion status')
        self.input.setToolTip('Choose completion statuses from the checklist.')
        self.findChildren(QPushButton)[1].hide()

    def edit_values(self):
        selected = self.toPlainText().splitlines()
        menu = QMenu(self)
        for value in dict.fromkeys(['Not started', 'Playing', 'Completed', '100% complete', 'On hold', 'Dropped'] + selected):
            action = QAction(value, menu)
            action.setCheckable(True)
            action.setChecked(value in selected)
            menu.addAction(action)
            action.toggled.connect(lambda checked, value=value: self.toggle_value(value, checked))
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def toggle_value(self, value, checked):
        selected = self.toPlainText().splitlines()
        selected = [entry for entry in selected if entry != value]
        if checked:
            selected.append(value)
        self.setPlainText('\n'.join(selected))


class LinksField(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)

    def add(self, name='', url=''):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        name_field, url_field = QLineEdit(name), QLineEdit(url)
        name_field.setFixedHeight(40)
        url_field.setFixedHeight(40)
        name_field.setPlaceholderText('Name')
        url_field.setPlaceholderText('https://…')
        layout.addWidget(name_field, 1)
        layout.addWidget(url_field, 3)
        row = (widget, name_field, url_field)
        for title, action, tooltip in [('↑', lambda: self.move(row, -1), 'Move link up'),
                                       ('↓', lambda: self.move(row, 1), 'Move link down'),
                                       ('×', lambda: self.remove(row), 'Remove link')]:
            button = QPushButton(title)
            button.setObjectName('compact')
            button.setFixedSize(32, 40)
            button.setToolTip(tooltip)
            button.clicked.connect(action)
            layout.addWidget(button)
        self.rows.append(row)
        self.layout.addWidget(widget)
        QTimer.singleShot(0, self.align_add_button)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.align_add_button)

    def align_add_button(self):
        button = getattr(self, 'add_button', None)
        if button is not None:
            width = self.rows[0][1].width() if self.rows else max(1, (self.width() - 128) // 4)
            button.setFixedWidth(width)

    def move(self, row, direction):
        index = self.rows.index(row)
        destination = index + direction
        if not 0 <= destination < len(self.rows):
            return
        self.rows.insert(destination, self.rows.pop(index))
        self.layout.removeWidget(row[0])
        self.layout.insertWidget(destination, row[0])

    def remove(self, row):
        self.rows.remove(row)
        self.layout.removeWidget(row[0])
        row[0].hide()
        row[0].deleteLater()

    def clear(self):
        for row in list(self.rows):
            self.remove(row)

    def values(self):
        return [{'Name': name.text().strip(), 'Url': url.text().strip()} for _, name, url in self.rows]
