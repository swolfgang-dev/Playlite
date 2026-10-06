"""Application download queue and a sliding tray over the game view."""
from dataclasses import dataclass, field
from pathlib import Path
import uuid
import json
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QEvent, QVariantAnimation, QEasingCurve, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QFrame, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget, QProgressBar, QMessageBox
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
    paused: bool = False
    metadata: dict = field(default_factory=dict)


class DownloadQueue(QObject):
    changed = pyqtSignal()

    def __init__(self,parent=None,storage=None):
        super().__init__(parent)
        self.entries=[]; self.active=None; self.stopped=False
        self.storage=Path(storage) if storage else None
        self.load()
        self.changed.connect(self.save)

    def load(self):
        if not self.storage or not self.storage.exists():return
        try:
            data=json.loads(self.storage.read_text())
            for item in data:
                row=Download(item['name'],item['destination'],None,id=item['id'],
                             state=item['state'],status=item['status'],progress=item.get('progress'),metadata=item.get('metadata',{}))
                if row.state in ('Queued','Downloading'):
                    row.state='Paused';row.status='Paused when Playlite closed · resume to continue'
                self.entries.append(row)
        except (OSError,ValueError,KeyError,TypeError):
            self.entries=[]

    def save(self):
        if not self.storage:return
        self.storage.parent.mkdir(parents=True,exist_ok=True)
        data=[{key:getattr(row,key) for key in ('name','destination','id','state','status','progress','metadata')} for row in self.entries]
        temporary=self.storage.with_suffix('.tmp');temporary.write_text(json.dumps(data));temporary.chmod(0o600);temporary.replace(self.storage)

    def ordered(self):
        rank={'Downloading':0,'Queued':1,'Failed':2,'Paused':3,'Cancelled':4,'Complete':5}
        return sorted(self.entries,key=lambda row:rank.get(row.state,3))

    def move_queued(self,row,direction):
        if self.stopped or row.state!='Queued' or direction not in (-1,1):return
        queued=[entry for entry in self.entries if entry.state=='Queued']
        if row not in queued:return
        target=queued.index(row)+direction
        if not 0<=target<len(queued):return
        other=queued[target]
        first=self.entries.index(row);second=self.entries.index(other)
        self.entries[first],self.entries[second]=self.entries[second],self.entries[first]
        self.changed.emit()

    def enqueue(self,name,destination,factory,metadata=None):
        if self.stopped:raise ValueError('The download queue is closing.')
        destination=str(Path(destination).expanduser().resolve())
        if any(row.destination==destination and row.state in ('Queued','Downloading') for row in self.entries):
            raise ValueError('That download folder is already queued.')
        row=Download(name,destination,factory,metadata=metadata or {});self.entries.append(row)
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
        row.state='Paused' if row.paused else 'Cancelled' if row.cancelled else 'Complete' if success else 'Failed'
        if row.paused:status='Paused · partial files retained'
        row.status=status;row.progress=100 if success and not row.cancelled else row.progress
        self.active=None;self.changed.emit();QTimer.singleShot(0,self.pump)

    def cancel(self,row):
        if row.state=='Queued':
            row.state='Cancelled';row.status='Removed from queue';self.changed.emit()
        elif row.state=='Paused':
            row.state='Cancelled';row.paused=False;row.status='Stopped · partial files retained';self.changed.emit()
        elif self.active is row and not row.cancelled:
            row.cancelled=True;row.status='Stopping download…';self.changed.emit()
            if row.controller:row.controller.cancel()

    def pause(self,row):
        if row.state=='Queued':
            row.state='Paused';row.status='Paused before starting';self.changed.emit()
        elif self.active is row and not row.cancelled:
            row.paused=True;row.cancelled=True;row.status='Pausing download…';self.changed.emit()
            if row.controller:row.controller.cancel()

    def retry(self,row):
        if row.state not in ('Failed','Cancelled','Paused') or not callable(row.factory):return
        if any(other is not row and other.destination==row.destination and other.state in ('Queued','Downloading') for other in self.entries):
            raise ValueError('That download folder is already queued.')
        if row.controller:
            dispose=getattr(row.controller,'dispose',None)
            if callable(dispose):dispose()
        row.controller=None;row.cancelled=False;row.paused=False;row.state='Queued';row.status='Waiting to resume…'
        self.changed.emit();QTimer.singleShot(0,self.pump)

    def clear_finished(self):
        for row in self.entries:
            if row.state in ('Complete','Failed','Cancelled') and row.controller:
                dispose=getattr(row.controller,'dispose',None)
                if callable(dispose):dispose()
        self.entries[:]=[row for row in self.entries if row.state not in ('Complete','Failed','Cancelled')]
        self.changed.emit()

    def shutdown(self):
        self.stopped=True
        for row in list(self.entries):
            self.pause(row)
            if self.active is row:row.state='Paused';row.status='Paused when Playlite closed · resume to continue'
        self.save()

    def confirm_close(self,parent):
        if not any(row.state in ('Queued','Downloading','Paused') for row in self.entries):return True
        return QMessageBox.warning(parent,'Downloads are unfinished',
            'Closing Playlite will pause unfinished downloads and stop isolated Steam and the VPN. Your download list and partial files will be kept.',
            QMessageBox.StandardButton.Close|QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Close


class DownloadsPanel(QFrame):
    def __init__(self,host,queue):
        super().__init__(host)
        self.queue=queue;self.opened=False;self.amount=0.;self.cards={}
        self.host_margins=host.viewportMargins() if hasattr(host,'viewportMargins') else None
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
        content=QWidget();self.rows=QVBoxLayout(content);self.rows.setContentsMargins(12,12,12,12);self.rows.setSpacing(12);self.rows.addStretch()
        scroll.setWidget(content);layout.addWidget(scroll,1)
        self.animation=QVariantAnimation(self);self.animation.setDuration(260);self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.valueChanged.connect(self.set_amount);self.animation.finished.connect(self.settle)
        host.installEventFilter(self);queue.changed.connect(self.refresh);self.refresh();self.hide()

    def eventFilter(self,watched,event):
        if watched is self.parentWidget() and event.type()==QEvent.Type.Resize:self.place()
        return super().eventFilter(watched,event)

    def place(self):
        host=self.parentWidget();height=min(460,max(160,round(host.height()*.65)))
        height=min(host.height(),height)
        visible_height=round(height*self.amount)
        if self.host_margins is not None:
            margins=self.host_margins
            host.setViewportMargins(margins.left(),margins.top(),margins.right(),margins.bottom()+visible_height)
        self.setGeometry(0,host.height()-visible_height,host.width(),height)
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
        waiting=[row for row in self.queue.entries if row.state=='Queued']
        self.summary.setText(f'{queued} waiting · '+('Downloading' if self.queue.active else 'Idle'))
        ids={row.id for row in self.queue.entries}
        for identifier in list(self.cards):
            if identifier not in ids:self.cards.pop(identifier)[0].deleteLater()
        for index,row in enumerate(self.queue.ordered()):
            if row.id not in self.cards:
                card=QFrame();card.setObjectName('downloadCard')
                set_style(card,
                    f'QFrame#downloadCard {{ background: {colour("#292b2e")}; border: 1px solid {colour("#45474b")}; border-radius: 8px; }}'
                    f'QFrame#downloadCard QPushButton {{ background: {colour("#3b4654")}; border: 1px solid {colour("#566477")}; }}'
                    f'QFrame#downloadCard QPushButton:hover {{ background: {colour("#4b5b70")}; }}'
                    f'QFrame#downloadCard QPushButton:pressed {{ background: {colour("#303c4b")}; }}'
                    f'QFrame#downloadCard QPushButton:disabled {{ background: {colour("#30343a")}; color: {colour("#7f8791")}; border-color: {colour("#45474b")}; }}')
                box=QVBoxLayout(card);box.setContentsMargins(14,12,14,12);box.setSpacing(10)
                line=QHBoxLayout();line.setSpacing(10);name=QLabel();name.setWordWrap(True);line.addWidget(name,1)
                up=QPushButton('↑');up.setToolTip('Move earlier in queue');up.setAccessibleName('Move earlier in queue')
                down=QPushButton('↓');down.setToolTip('Move later in queue');down.setAccessibleName('Move later in queue')
                up.clicked.connect(lambda checked=False,row=row:self.queue.move_queued(row,-1))
                down.clicked.connect(lambda checked=False,row=row:self.queue.move_queued(row,1))
                line.addWidget(up);line.addWidget(down)
                action=QPushButton();action.clicked.connect(lambda checked=False,row=row:self.action(row))
                library=QPushButton('Add to Playlite')
                library.clicked.connect(lambda checked=False,row=row:row.controller.add_to_library())
                pause=QPushButton('Pause');pause.clicked.connect(lambda checked=False,row=row:self.queue.pause(row))
                retry=QPushButton();retry.clicked.connect(lambda checked=False,row=row:self.retry(row))
                line.addWidget(pause);line.addWidget(retry)
                line.addWidget(library);line.addWidget(action);box.addLayout(line)
                status=QLabel();status.setWordWrap(True);box.addWidget(status)
                bar=QProgressBar();bar.setRange(0,1000);box.addWidget(bar)
                self.rows.insertWidget(self.rows.count()-1,card)
                self.cards[row.id]=(card,name,status,bar,action,library,pause,retry,up,down)
            card,name,status,bar,action,library,pause,retry,up,down=self.cards[row.id]
            self.rows.removeWidget(card);self.rows.insertWidget(index,card)
            up.setVisible(row.state=='Queued');down.setVisible(row.state=='Queued')
            up.setEnabled(row.state=='Queued' and waiting.index(row)>0)
            down.setEnabled(row.state=='Queued' and waiting.index(row)<len(waiting)-1)
            pause.setVisible(row.state in ('Queued','Downloading'));pause.setEnabled(not row.cancelled)
            retry.setText('Resume' if row.state=='Paused' else 'Retry')
            retry.setVisible(row.state in ('Failed','Cancelled','Paused'));retry.setEnabled(callable(row.factory))
            library.setVisible(row.state=='Complete' and callable(getattr(row.controller,'add_to_library',None)))
            name.setToolTip(row.destination)
            name.setText(row.name);name.setTextFormat(Qt.TextFormat.PlainText)
            status.setText(f'{"Stopped" if row.state=="Cancelled" else row.state} · {row.status}');status.setTextFormat(Qt.TextFormat.PlainText)
            bar.setRange(0,0 if row.state=='Downloading' and row.progress is None else 1000)
            bar.setValue(round((row.progress or 0)*10));bar.setVisible(row.state in ('Downloading','Complete'))
            action.setText('Open folder' if row.state=='Complete' else 'Cancel')
            action.setVisible(row.state in ('Queued','Downloading','Complete','Paused'));action.setEnabled(not row.cancelled or row.state=='Paused')

    def action(self,row):
        if row.state=='Complete':QDesktopServices.openUrl(QUrl.fromLocalFile(row.destination))
        else:self.queue.cancel(row)

    def retry(self,row):
        try:self.queue.retry(row)
        except ValueError as error:QMessageBox.warning(self,'Cannot retry download',str(error))


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
