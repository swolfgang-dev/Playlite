"""Shared task history for downloads and plugin work."""
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import uuid
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QLabel,
    QPlainTextEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QHeaderView)
from .lifecycle import run_dialog

ACTIVE = {'Queued', 'Running', 'Waiting', 'Downloading', 'Uploading'}


class BackgroundTasks(QObject):
    changed = pyqtSignal()

    def __init__(self, parent=None, storage=None):
        super().__init__(parent)
        self.storage = Path(storage) if storage else None
        self.records = {}
        self.callbacks = {}
        if self.storage and self.storage.exists():
            try:
                for row in json.loads(self.storage.read_text()):
                    if row['state'] in ACTIVE:
                        row.update(state='Interrupted', summary='Playlite closed before completion was recorded.')
                    self.records[row['id']] = row
            except (OSError, ValueError, KeyError, TypeError):
                self.records = {}

    def update(self, identity=None, **values):
        identity = identity or uuid.uuid4().hex
        row = self.records.setdefault(identity, dict(id=identity, title='', kind='', state='Queued', summary='', details='', progress=None))
        for key in ('retry', 'cancel'):
            if key in values:
                self.callbacks.setdefault(identity, {})[key] = values.pop(key)
        row.update(values, updated=datetime.now(timezone.utc).isoformat(timespec='microseconds'))
        if self.storage:
            self._save()
        self.changed.emit()
        return identity

    def _save(self):
        try:
            self.storage.parent.mkdir(parents=True, exist_ok=True)
            temp = self.storage.with_suffix('.tmp')
            # Keep active work plus the latest 200 completed tasks.
            rows = sorted(self.records.values(), key=lambda r: r['updated'], reverse=True)
            finished = [r for r in rows if r['state'] not in ACTIVE][:200]
            retained = [r for r in rows if r['state'] in ACTIVE] + finished
            self.records = {r['id']: r for r in retained}
            self.callbacks = {key: value for key, value in self.callbacks.items() if key in self.records}
            temp.write_text(json.dumps(retained, indent=2))
            temp.chmod(0o600)
            temp.replace(self.storage)
        except OSError:
            logging.exception('Could not save background task history')

    def follow_downloads(self, queue):
        def refresh():
            current = {'download-' + row.id for row in queue.entries}
            for identity in list(self.callbacks):
                if identity.startswith('download-') and identity not in current:
                    self.callbacks.pop(identity)
            for row in queue.entries:
                identity = 'download-' + row.id
                existing = self.records.get(identity, {})
                if all(existing.get(key) == value for key, value in {'title': row.name, 'state': row.state, 'summary': row.status, 'progress': row.progress}.items()):
                    continue
                self.update(identity, title=row.name, kind='Download', state=row.state,
                            summary=row.status, progress=row.progress, details='Destination: ' + row.destination + '\n' + row.status,
                            retry=(lambda row=row: queue.retry(row)) if callable(row.factory) and row.state in ('Failed', 'Cancelled', 'Paused') else None,
                            cancel=(lambda row=row: queue.cancel(row)) if row.state in ('Queued', 'Downloading') else None)
        queue.changed.connect(refresh)
        refresh()


def show_tasks(window):
    registry = window.background_tasks
    dialog = QDialog(window); dialog.setWindowTitle('Background tasks'); dialog.resize(850, 580)
    layout = QVBoxLayout(dialog)
    tree = QTreeWidget(); tree.setHeaderLabels(['Task', 'Type', 'State', 'Progress']); tree.setRootIsDecorated(False)
    tree.header().setStretchLastSection(False)
    tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    for column in (1, 2, 3): tree.header().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
    layout.addWidget(tree)
    summary = QLabel(); summary.setWordWrap(True); layout.addWidget(summary)
    toggle = QPushButton('Show details'); toggle.setCheckable(True); layout.addWidget(toggle)
    details = QPlainTextEdit(); details.setReadOnly(True); details.hide(); layout.addWidget(details)
    toggle.toggled.connect(details.setVisible)
    toggle.toggled.connect(lambda on: toggle.setText('Hide details' if on else 'Show details'))
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    copy = buttons.addButton('Copy log', QDialogButtonBox.ButtonRole.ActionRole)
    retry = buttons.addButton('Retry', QDialogButtonBox.ButtonRole.ActionRole)
    cancel = buttons.addButton('Cancel task', QDialogButtonBox.ButtonRole.ActionRole)
    layout.addWidget(buttons); buttons.rejected.connect(dialog.reject)
    def current():
        item = tree.currentItem()
        return item.data(0, 256) if item else None
    def selected():
        identity = current(); row = registry.records.get(identity, {})
        summary.setText(row.get('summary', 'Select a task.'))
        details.setPlainText(row.get('details', ''))
        callbacks = registry.callbacks.get(identity, {})
        retry.setEnabled(row.get('state') not in ACTIVE and callable(callbacks.get('retry')))
        cancel.setEnabled(row.get('state') in ACTIVE and callable(callbacks.get('cancel')))
    def refresh():
        identity = current(); tree.blockSignals(True); tree.clear()
        for row in sorted(sorted(registry.records.values(), key=lambda r: r['updated'], reverse=True), key=lambda r: r['state'] not in ACTIVE):
            progress = row.get('progress')
            item = QTreeWidgetItem([row['title'], row['kind'], row['state'], '' if progress is None else f'{progress:.0f}%'])
            item.setData(0, 256, row['id'])
            for column in range(4): item.setToolTip(column, item.text(column))
            tree.addTopLevelItem(item)
            if row['id'] == identity: tree.setCurrentItem(item)
        tree.blockSignals(False)
        if tree.currentItem() is None and tree.topLevelItemCount(): tree.setCurrentItem(tree.topLevelItem(0))
        selected()
    def invoke(key):
        callback = registry.callbacks.get(current(), {}).get(key)
        if callable(callback): callback()
    retry.clicked.connect(lambda: invoke('retry')); cancel.clicked.connect(lambda: invoke('cancel'))
    copy.clicked.connect(lambda: QApplication.clipboard().setText(summary.text() + '\n\n' + details.toPlainText()))
    tree.currentItemChanged.connect(lambda *_: selected())
    registry.changed.connect(refresh); refresh()
    try: run_dialog(dialog)
    finally: registry.changed.disconnect(refresh)
