"""Shared spacing and dialog sizing for core and plugin windows."""
import atexit
from PyQt6 import sip
from PyQt6.QtCore import QObject, QEvent
from PyQt6.QtWidgets import (QDialog, QFileDialog, QMessageBox, QFormLayout,
    QHBoxLayout, QVBoxLayout, QGridLayout, QLayout, QWidget, QGroupBox,
    QDialogButtonBox, QAbstractItemView, QAbstractSpinBox, QComboBox,
    QTextEdit, QPlainTextEdit)

OUTER = 24
SECTION = 24
CARD = 16
ROW = 12
RELATED = 8


def action_row(*buttons):
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(RELATED)
    for button in buttons:
        row.addWidget(button)
    row.addStretch()
    return row


def configure_dialog(dialog):
    """Normalize application layouts, keeping Qt's internal controls untouched."""
    if isinstance(dialog, (QFileDialog, QMessageBox)) or dialog.property('playliteLayoutReady'):
        return
    dialog.setProperty('playliteLayoutReady', True)
    root = dialog.layout()
    if root is not None:
        root.setContentsMargins(OUTER, OUTER, OUTER, OUTER)
        root.setSpacing(CARD)
    internal = (QAbstractItemView, QAbstractSpinBox, QComboBox, QTextEdit,
                QPlainTextEdit, QDialogButtonBox)
    for layout in dialog.findChildren(QLayout):
        if layout is root:
            continue
        parent = layout.parent()
        while parent is not None and not isinstance(parent, QWidget):
            parent = parent.parent()
        ancestor = parent
        skip = False
        while ancestor is not None and ancestor is not dialog:
            if isinstance(ancestor, internal):
                skip = True
                break
            ancestor = ancestor.parentWidget()
        if skip:
            continue
        if isinstance(layout, QFormLayout):
            layout.setVerticalSpacing(ROW)
            layout.setHorizontalSpacing(CARD)
        elif isinstance(layout, QHBoxLayout):
            # Zero spacing belongs to split buttons and other joined controls.
            if layout.spacing() != 0:
                layout.setSpacing(RELATED)
        elif isinstance(layout, QGridLayout):
            if layout.horizontalSpacing() != 0:
                layout.setHorizontalSpacing(ROW)
            if layout.verticalSpacing() != 0:
                layout.setVerticalSpacing(ROW)
        elif isinstance(layout, QVBoxLayout) and layout.spacing() != 0:
            # Preserve deliberately larger gaps between sections.
            layout.setSpacing(SECTION if layout.spacing() >= SECTION else ROW)
        if isinstance(parent, QGroupBox) and parent.layout() is layout:
            layout.setContentsMargins(CARD, CARD, CARD, CARD)
    # Keep first-show dimensions within the available desktop, also at 200% scale.
    available = dialog.screen().availableGeometry()
    width, height = max(320, available.width() - 48), max(240, available.height() - 48)
    dialog.setMinimumSize(min(dialog.minimumWidth(), width), min(dialog.minimumHeight(), height))
    dialog.resize(min(dialog.width(), width), min(dialog.height(), height))


class DialogLayouts(QObject):
    def detach(self):
        if not sip.isdeleted(self) and self.parent() is not None:
            self.parent().removeEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show and isinstance(watched, QDialog):
            configure_dialog(watched)
        return False


def install(app):
    if not hasattr(app, '_dialog_layouts'):
        app._dialog_layouts = DialogLayouts(app)
        app.installEventFilter(app._dialog_layouts)
        app.aboutToQuit.connect(app._dialog_layouts.detach)
        # Embedded/test applications may never enter exec(), and therefore do
        # not emit aboutToQuit before Python starts destroying Qt wrappers.
        atexit.register(app._dialog_layouts.detach)


def scroll_dialog_body(dialog, footer):
    """Give tall forms a scrolling body while their action footer stays visible."""
    from PyQt6.QtWidgets import QScrollArea, QFrame
    root = dialog.layout()
    if not isinstance(root, QVBoxLayout):
        raise ValueError('A scrolling dialog needs a vertical root layout.')
    footer_index = next((index for index in range(root.count())
                         if root.itemAt(index).layout() is footer or root.itemAt(index).widget() is footer), -1)
    if footer_index < 0:
        raise ValueError('The footer must belong directly to the dialog layout.')
    body = QWidget()
    content = QVBoxLayout(body)
    content.setContentsMargins(0, 0, 0, 0)
    content.setSpacing(ROW)
    # Recalculate the body's minimum when sections expand or collapse. The
    # viewport supplies spare space; the form supplies its natural minimum.
    content.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
    retained = None
    while root.count():
        stretch = root.stretch(0)
        item = root.takeAt(0)
        if item.layout() is footer or item.widget() is footer:
            retained = item
        elif item.widget() is not None:
            content.addWidget(item.widget(), stretch, item.alignment())
        elif item.layout() is not None:
            child_layout = item.layout()
            child_layout.setParent(None)
            content.addLayout(child_layout, stretch)
        else:
            content.addItem(item)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(body)
    root.addWidget(scroll, 1)
    if retained is not None:
        root.addItem(retained)
    return scroll


def insert_form_row_after(form, anchor, *row):
    """Place a contribution relative to an owned control, independent of rows."""
    index, _ = (form.getLayoutPosition(anchor) if isinstance(anchor, QLayout)
                else form.getWidgetPosition(anchor))
    if index < 0:
        raise ValueError('The anchor must belong directly to the form.')
    form.insertRow(index + 1, *row)
