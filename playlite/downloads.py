"""Application download queue and a sliding tray over the game view."""
from dataclasses import dataclass, field
from pathlib import Path
import uuid
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QEvent, QVariantAnimation, QEasingCurve, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QFrame, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget, QProgressBar
from .theme import set_style, colour


@dataclass
class Download:
    name: str
    destination: str
    factory: object = field(repr=False)
    id: str = field(default_factory=lambda:uuid.uuid4().hex)
    state: str = 'Queued'
    status: str = 'Waiting to download'
    progress: float | None = None
    controller: object = field(default=None,repr=False)
    cancelled: bool = False


class DownloadQueue(QObject):
    changed = pyqtSignal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.entries=[]; self.active=None; self.stopped=False

    def enqueue(self,name,destination,factory):
        if self.stopped:raise ValueError('The download queue is closing.')
        destination=str(Path(destination).expanduser().resolve())
        if any(row.destination==destination and row.state in ('Queued','Downloading') for row in self.entries):
            raise ValueError('That download folder is already queued.')
        row=Download(name,destination,factory);self.entries.append(row)
        self.changed.emit();QTimer.singleShot(0,self.pump)
        return row

    def pump(self):
        if self.stopped or self.active:return
        row=next((row for row in self.entries if row.state=='Queued'),None)
        if row is None:return
        self.active=row;row.state='Downloading';row.status='Starting download…'
        self.changed.emit()
        try:
            row.controller=row.factory(self,row)
            row.controller.start()
        except Exception as error:self.finish(row,False,str(error))

    def update(self,row,progress,status):
        if self.active is not row or row.cancelled:return
        row.progress=None if progress is None else min(100,max(0,float(progress)))
        row.status=status;self.changed.emit()

    def finish(self,row,success,status):
        if self.active is not row:return
        row.state='Cancelled' if row.cancelled else 'Complete' if success else 'Failed'
        row.status=status;row.progress=100 if success and not row.cancelled else row.progress
        self.active=None;row.factory=None;self.changed.emit();QTimer.singleShot(0,self.pump)

    def cancel(self,row):
        if row.state=='Queued':
            row.state='Cancelled';row.status='Removed from queue';row.factory=None;self.changed.emit()
        elif self.active is row and not row.cancelled:
            row.cancelled=True;row.status='Stopping download…';self.changed.emit()
            if row.controller:row.controller.cancel()

    def clear_finished(self):
        for row in self.entries:
            if row.state not in ('Queued','Downloading') and row.controller:
                dispose=getattr(row.controller,'dispose',None)
                if callable(dispose):dispose()
        self.entries[:]=[row for row in self.entries if row.state in ('Queued','Downloading')]
        self.changed.emit()

    def shutdown(self):
        self.stopped=True
        for row in list(self.entries):self.cancel(row)


class DownloadsPanel(QFrame):
    def __init__(self,host,queue):
        super().__init__(host)
        self.queue=queue;self.opened=False;self.amount=0.;self.cards={}
        self.setObjectName('downloadsPanel')
        set_style(self,f'QFrame#downloadsPanel {{ background: {colour("#202123")}; border: 1px solid {colour("#45474b")}; border-top-left-radius: 12px; border-top-right-radius: 12px; }}')
        layout=QVBoxLayout(self);layout.setContentsMargins(20,16,20,16);layout.setSpacing(12)
        title=QLabel('Downloads');title.setStyleSheet('font-weight: bold; font-size: 17px;')
        clear=QPushButton('Clear finished');clear.clicked.connect(queue.clear_finished)
        close=QPushButton('Close');close.clicked.connect(lambda:self.set_open(False))
        header=QHBoxLayout();header.setSpacing(10);header.addWidget(title);header.addStretch();header.addWidget(clear);header.addWidget(close)
        layout.addLayout(header)
        self.summary=QLabel('No downloads queued');layout.addWidget(self.summary)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame)
        content=QWidget();self.rows=QVBoxLayout(content);self.rows.setContentsMargins(0,0,0,0);self.rows.setSpacing(12);self.rows.addStretch()
        scroll.setWidget(content);layout.addWidget(scroll,1)
        self.animation=QVariantAnimation(self);self.animation.setDuration(260);self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.valueChanged.connect(self.set_amount);self.animation.finished.connect(self.settle)
        host.installEventFilter(self);queue.changed.connect(self.refresh);self.hide()

    def eventFilter(self,watched,event):
        if watched is self.parentWidget() and event.type()==QEvent.Type.Resize:self.place()
        return super().eventFilter(watched,event)

    def place(self):
        host=self.parentWidget();height=min(460,max(160,round(host.height()*.65)))
        height=min(host.height(),height)
        self.setGeometry(0,host.height()-round(height*self.amount),host.width(),height)
        self.raise_()

    def set_amount(self,value):self.amount=float(value);self.place()

    def set_open(self,opened):
        self.opened=opened;self.animation.stop();self.show();self.raise_()
        self.animation.setStartValue(self.amount);self.animation.setEndValue(1. if opened else 0.)
        self.animation.start()

    def settle(self):
        if not self.opened:self.hide()

    def refresh(self):
        queued=sum(row.state=='Queued' for row in self.queue.entries)
        self.summary.setText(f'{queued} waiting · '+('Downloading' if self.queue.active else 'Idle'))
        ids={row.id for row in self.queue.entries}
        for identifier in list(self.cards):
            if identifier not in ids:self.cards.pop(identifier)[0].deleteLater()
        for row in self.queue.entries:
            if row.id not in self.cards:
                card=QFrame();box=QVBoxLayout(card);box.setContentsMargins(12,10,12,10)
                line=QHBoxLayout();line.setSpacing(10);name=QLabel();name.setWordWrap(True);line.addWidget(name,1)
                action=QPushButton();action.clicked.connect(lambda checked=False,row=row:self.action(row))
                library=QPushButton('Add to Playlite')
                library.clicked.connect(lambda checked=False,row=row:row.controller.add_to_library())
                line.addWidget(library);line.addWidget(action);box.addLayout(line)
                status=QLabel();status.setWordWrap(True);box.addWidget(status)
                bar=QProgressBar();bar.setRange(0,1000);box.addWidget(bar)
                self.rows.insertWidget(self.rows.count()-1,card)
                self.cards[row.id]=(card,name,status,bar,action,library)
            card,name,status,bar,action,library=self.cards[row.id]
            library.setVisible(row.state=='Complete' and callable(getattr(row.controller,'add_to_library',None)))
            name.setToolTip(row.destination)
            name.setText(row.name);name.setTextFormat(Qt.TextFormat.PlainText)
            status.setText(f'{row.state} · {row.status}');status.setTextFormat(Qt.TextFormat.PlainText)
            bar.setRange(0,0 if row.state=='Downloading' and row.progress is None else 1000)
            bar.setValue(round((row.progress or 0)*10));bar.setVisible(row.state in ('Downloading','Complete'))
            action.setText('Remove' if row.state=='Queued' else 'Open folder' if row.state=='Complete' else 'Cancel')
            action.setVisible(row.state in ('Queued','Downloading','Complete'));action.setEnabled(not row.cancelled)

    def action(self,row):
        if row.state=='Complete':QDesktopServices.openUrl(QUrl.fromLocalFile(row.destination))
        else:self.queue.cancel(row)


class DownloadsButton(QObject):
    def __init__(self,sidebar,panel,queue):
        super().__init__(sidebar)
        self.sidebar=sidebar;self.panel=panel;self.queue=queue
        sidebar.setViewportMargins(0,0,0,56)
        self.button=QPushButton(sidebar);self.button.setToolTip('Downloads');self.button.setAccessibleName('Downloads')
        self.button.clicked.connect(lambda:panel.set_open(not panel.opened))
        sidebar.installEventFilter(self);queue.changed.connect(self.refresh);self.refresh()

    def eventFilter(self,watched,event):
        if watched is self.sidebar and event.type()==QEvent.Type.Resize:self.refresh()
        return super().eventFilter(watched,event)

    def refresh(self):
        count=sum(row.state in ('Queued','Downloading') for row in self.queue.entries)
        text='Downloads' if self.sidebar.width()>=150 else '↓'
        self.button.setText(text+(f' ({count})' if count else ''))
        self.button.setGeometry(8,max(0,self.sidebar.height()-48),max(24,self.sidebar.width()-16),40)
        self.button.raise_()
