"""Application download queue and a sliding tray over the game view."""
from dataclasses import dataclass, field
from pathlib import Path
import uuid
import json
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QEvent, QVariantAnimation, QEasingCurve, Qt, QUrl, QSize
from PyQt6.QtGui import QDesktopServices, QColor, QIcon
from PyQt6.QtWidgets import QFrame, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget, QProgressBar, QMessageBox
from .theme import set_style, colour
from .desktop import open_folder


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

    def remove_completed(self,row):
        if row.state!='Complete' or row not in self.entries:return
        self.entries.remove(row)
        self.changed.emit()

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
            'Closing Playlite will pause unfinished downloads. Your download list and partial files will be kept.',
            QMessageBox.StandardButton.Close|QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Close


class DownloadsPanel(QFrame):
    def __init__(self,host,queue):
        super().__init__(host)
        self.queue=queue;self.opened=False;self.amount=0.;self.cards={};self.transparency=0
        self.host_margins=host.viewportMargins() if hasattr(host,'viewportMargins') else None
        self.active_strip=QFrame(host)
        self.active_strip.setObjectName('activeDownloadStrip')
        set_style(self.active_strip, 'QFrame#activeDownloadStrip { background: #202123; border-top: 1px solid #45474b; }')
        strip_layout=QVBoxLayout(self.active_strip);strip_layout.setContentsMargins(16,8,16,8);strip_layout.setSpacing(6)
        strip_line=QHBoxLayout()
        self.active_label=QLabel();self.active_label.setTextFormat(Qt.TextFormat.PlainText)
        strip_line.addWidget(self.active_label,1)
        self.expand_button=QPushButton()
        self.expand_button.setIcon(QIcon(str(Path(__file__).parent/'assets/downloads.svg')))
        self.expand_button.setIconSize(QSize(24,24))
        self.expand_button.setFixedSize(40,40)
        set_style(self.expand_button,'padding: 0;')
        self.expand_button.setToolTip('Show downloads')
        self.expand_button.setAccessibleName('Show downloads')
        self.expand_button.clicked.connect(lambda:self.set_open(not self.opened))
        strip_line.addWidget(self.expand_button);strip_layout.addLayout(strip_line)
        self.active_progress=QProgressBar();self.active_progress.setFixedHeight(8);self.active_progress.setTextVisible(False)
        progress_policy=self.active_progress.sizePolicy()
        progress_policy.setRetainSizeWhenHidden(True)
        self.active_progress.setSizePolicy(progress_policy)
        strip_layout.addWidget(self.active_progress)
        self.active_strip.hide()
        self.strip_present=False
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
        set_style(scroll,'QScrollArea { background: transparent; border: 0; } QScrollArea > QWidget > QWidget { background: transparent; }')
        content=QWidget();self.rows=QVBoxLayout(content);self.rows.setContentsMargins(12,12,12,12);self.rows.setSpacing(12);self.rows.addStretch()
        scroll.setWidget(content);layout.addWidget(scroll,1)
        self.animation=QVariantAnimation(self);self.animation.setDuration(260);self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.valueChanged.connect(self.set_amount);self.animation.finished.connect(self.settle)
        host.installEventFilter(self);queue.changed.connect(self.refresh);self.refresh();self.hide()

    def eventFilter(self,watched,event):
        if watched is self.parentWidget() and event.type()==QEvent.Type.Resize:self.place()
        return super().eventFilter(watched,event)

    def transparent_colour(self,value):
        red,green,blue,_=QColor(colour(value)).getRgb()
        return f'rgba({red}, {green}, {blue}, {round(255*(1-self.transparency/100))})'

    def set_transparency(self,value):
        self.transparency=max(0,min(100,value))
        background=self.transparent_colour('#202123')
        set_style(self,f'QFrame#downloadsPanel {{ background: {background}; border: 1px solid #45474b; border-top-left-radius: 12px; border-top-right-radius: 12px; }}')
        set_style(self.active_strip,f'QFrame#activeDownloadStrip {{ background: {background}; border-top: 1px solid #45474b; }}')
        for card,*_ in self.cards.values():
            template=card.property('_theme_stylesheet')
            import re
            template=re.sub(r'(QFrame#downloadCard \{ background: )[^;]+',lambda match:match[1]+self.transparent_colour('#292b2e'),template)
            set_style(card,template)

    def place(self):
        self.active_progress.setVisible(not self.opened)
        host=self.parentWidget();strip_height=min(host.height(),self.active_strip.sizeHint().height()) if self.strip_present else 0
        self.active_strip.setGeometry(0,host.height()-strip_height,host.width(),strip_height)
        self.active_strip.setVisible(self.strip_present)
        self.active_strip.raise_()
        content_height=sum(card[0].sizeHint().height() for card in self.cards.values())
        content_height+=max(0,len(self.cards)-1)*self.rows.spacing()+self.rows.contentsMargins().top()+self.rows.contentsMargins().bottom()
        height=min(max(160,content_height+120),max(160,round(host.height()*.5)))
        height=min(max(0,host.height()-strip_height),height)
        visible_height=round(height*self.amount)
        if self.host_margins is not None:
            margins=self.host_margins
            host.setViewportMargins(margins.left(),margins.top(),margins.right(),margins.bottom()+visible_height+strip_height)
        self.setGeometry(0,host.height()-strip_height-visible_height,host.width(),height)
        self.raise_()
        self.active_strip.raise_()

    def set_amount(self,value):self.amount=float(value);self.place()

    def set_open(self,opened):
        self.opened=opened;self.animation.stop();self.show();self.raise_()
        self.expand_button.setToolTip('Hide downloads' if opened else 'Show downloads')
        self.expand_button.setAccessibleName(self.expand_button.toolTip())
        self.animation.setStartValue(self.amount);self.animation.setEndValue(1. if opened else 0.)
        self.animation.start()

    def settle(self):
        if not self.opened:self.hide()

    def refresh(self):
        queued=sum(row.state=='Queued' for row in self.queue.entries)
        waiting=[row for row in self.queue.entries if row.state=='Queued']
        active=self.queue.active or next((row for row in self.queue.entries if row.state in ('Queued','Paused')),None)
        self.strip_present=active is not None
        if active:
            self.active_label.setText(f'{active.name} · {active.state}' + (f' · {queued} waiting' if queued else ''))
            self.active_label.setToolTip(active.status)
            self.active_progress.setRange(0,0 if active.state=='Downloading' and active.progress is None else 1000)
            self.active_progress.setValue(round((active.progress or 0)*10))
        self.place()
        self.summary.setText(f'{queued} waiting · '+('Downloading' if self.queue.active else 'Idle'))
        ids={row.id for row in self.queue.entries}
        for identifier in list(self.cards):
            if identifier not in ids:self.cards.pop(identifier)[0].deleteLater()
        for index,row in enumerate(self.queue.ordered()):
            if row.id not in self.cards:
                card=QFrame();card.setObjectName('downloadCard')
                set_style(card,
                    f'QFrame#downloadCard {{ background: {self.transparent_colour("#292b2e")}; border: 1px solid {colour("#45474b")}; border-radius: 8px; }}'
                    f'QFrame#downloadCard QPushButton {{ background: {colour("#3b4654")}; border: 1px solid {colour("#566477")}; }}'
                    f'QFrame#downloadCard QPushButton:hover {{ background: {colour("#4b5b70")}; }}'
                    f'QFrame#downloadCard QPushButton:pressed {{ background: {colour("#303c4b")}; }}'
                    f'QFrame#downloadCard QPushButton:disabled {{ background: {colour("#30343a")}; color: {colour("#7f8791")}; border-color: {colour("#45474b")}; }}')
                box=QVBoxLayout(card);box.setContentsMargins(14,12,14,12);box.setSpacing(10)
                line=QHBoxLayout();line.setSpacing(10);name=QLabel();name.setWordWrap(True);line.addWidget(name,1)
                set_style(name,'font-weight: bold; font-size: 15px;')
                up=QPushButton('↑');up.setToolTip('Move earlier in queue');up.setAccessibleName('Move earlier in queue')
                down=QPushButton('↓');down.setToolTip('Move later in queue');down.setAccessibleName('Move later in queue')
                up.clicked.connect(lambda checked=False,row=row:self.queue.move_queued(row,-1))
                down.clicked.connect(lambda checked=False,row=row:self.queue.move_queued(row,1))
                line.addWidget(up);line.addWidget(down)
                action=QPushButton();action.clicked.connect(lambda checked=False,row=row:self.action(row))
                library=QPushButton('Add to Playlite')
                library.clicked.connect(lambda checked=False,row=row:self.add_to_library(row))
                pause=QPushButton('Pause');pause.clicked.connect(lambda checked=False,row=row:self.queue.pause(row))
                retry=QPushButton();retry.clicked.connect(lambda checked=False,row=row:self.retry(row))
                line.addWidget(pause);line.addWidget(retry)
                line.addWidget(library);line.addWidget(action);box.addLayout(line)
                card.remove_button=QPushButton('Remove')
                card.remove_button.setToolTip('Remove this completed entry. Downloaded files are kept.')
                card.remove_button.clicked.connect(lambda checked=False,row=row:self.queue.remove_completed(row))
                line.addWidget(card.remove_button)
                name.ensurePolished()
                name.setFixedHeight(max(44,name.fontMetrics().height()*2))
                status=QLabel();status.setWordWrap(True)
                status.ensurePolished()
                status.setFixedHeight(status.fontMetrics().lineSpacing()*2)
                status.metrics_label=QLabel();status.metrics_label.setTextFormat(Qt.TextFormat.PlainText)
                statistics=QHBoxLayout();statistics.addWidget(status,1);statistics.addWidget(status.metrics_label)
                box.addLayout(statistics)
                bar=QProgressBar();bar.setRange(0,1000);bar.setTextVisible(False);bar.setFixedHeight(8)
                set_style(bar,'QProgressBar { background: #101112; border: 0; border-radius: 4px; } QProgressBar::chunk { background: #2196f3; border-radius: 4px; }')
                bar.percent_label=QLabel();bar.percent_label.setMinimumWidth(42);bar.percent_label.setAlignment(Qt.AlignmentFlag.AlignRight)
                for progress_widget in (bar,bar.percent_label):
                    policy=progress_widget.sizePolicy();policy.setRetainSizeWhenHidden(True);progress_widget.setSizePolicy(policy)
                progress_line=QHBoxLayout();progress_line.addWidget(bar,1);progress_line.addWidget(bar.percent_label)
                box.addLayout(progress_line)
                self.rows.insertWidget(self.rows.count()-1,card)
                self.cards[row.id]=(card,name,status,bar,action,library,pause,retry,up,down)
            card,name,status,bar,action,library,pause,retry,up,down=self.cards[row.id]
            card.remove_button.setVisible(row.state=='Complete')
            self.rows.removeWidget(card);self.rows.insertWidget(index,card)
            up.setVisible(row.state=='Queued');down.setVisible(row.state=='Queued')
            up.setEnabled(row.state=='Queued' and waiting.index(row)>0)
            down.setEnabled(row.state=='Queued' and waiting.index(row)<len(waiting)-1)
            pause.setVisible(row.state in ('Queued','Downloading'));pause.setEnabled(not row.cancelled)
            retry.setText('Resume' if row.state=='Paused' else 'Retry')
            retry.setVisible(row.state in ('Failed','Cancelled','Paused'));retry.setEnabled(callable(row.factory))
            library.setVisible(row.state=='Complete' and callable(getattr(row.controller,'add_to_library',None)))
            added = bool(row.metadata.get('library_game_id'))
            library.setText('Added' if added else 'Add to Playlite')
            library.setEnabled(not added)
            name.setToolTip(row.destination)
            name.setText(row.name);name.setTextFormat(Qt.TextFormat.PlainText)
            state='Stopped' if row.state=='Cancelled' else row.state
            parts=[part.strip() for part in row.status.split('·')]
            if parts and parts[0].casefold()==state.casefold():parts.pop(0)
            detail=' · '.join(parts)
            transferred=next((part for part in parts if '/' in part and not part.lower().startswith('disk') and '/s' not in part),None)
            metrics=[part for part in parts if '/s' in part or 'remaining' in part]
            status.setText(f'{state} · {transferred}' if row.state=='Downloading' and transferred else state+(f' · {detail}' if detail else ''))
            status.setTextFormat(Qt.TextFormat.PlainText);status.setToolTip(row.status)
            status.metrics_label.setText(' · '.join(metrics) if transferred and row.state=='Downloading' else '')
            bar.setRange(0,0 if row.state=='Downloading' and row.progress is None else 1000)
            bar.setValue(round((row.progress or 0)*10));bar.setVisible(row.state in ('Downloading','Complete'))
            bar.percent_label.setText(f'{row.progress:.0f}%' if row.progress is not None else '')
            bar.percent_label.setVisible(row.state in ('Downloading','Complete'))
            action.setText('Open folder' if row.state=='Complete' else 'Cancel')
            set_style(action,'' if row.state=='Complete' else 'QPushButton { background: transparent; border: 1px solid #45474b; } QPushButton:hover { background: #30343a; }')
            action.setVisible(row.state in ('Queued','Downloading','Complete','Paused'));action.setEnabled(not row.cancelled or row.state=='Paused')
        self.place()

    def add_to_library(self, row):
        if row.metadata.get('library_game_id'):
            return
        identity = row.controller.add_to_library()
        if isinstance(identity, str) and identity:
            row.metadata['library_game_id'] = identity
            self.queue.changed.emit()

    def action(self,row):
        if row.state=='Complete':open_folder(row.destination)
        else:self.queue.cancel(row)

    def retry(self,row):
        try:self.queue.retry(row)
        except ValueError as error:QMessageBox.warning(self,'Cannot retry download',str(error))


class DownloadsButton(QObject):
    def __init__(self,sidebar,panel,queue,toolbar=False):
        super().__init__(sidebar)
        self.sidebar=sidebar;self.panel=panel;self.queue=queue;self.toolbar=toolbar
        if not toolbar:sidebar.setViewportMargins(0,0,0,56)
        self.button=QPushButton(sidebar);self.button.setToolTip('Downloads');self.button.setAccessibleName('Downloads')
        self.button.clicked.connect(lambda:panel.set_open(not panel.opened))
        sidebar.installEventFilter(self);queue.changed.connect(self.refresh);self.refresh()

    def eventFilter(self,watched,event):
        if watched is self.sidebar and event.type()==QEvent.Type.Resize:self.refresh()
        return super().eventFilter(watched,event)

    def refresh(self):
        count=sum(row.state in ('Queued','Downloading') for row in self.queue.entries)
        if self.toolbar:
            self.button.setIcon(QIcon(str(Path(__file__).parent/'assets/downloads.svg')))
            self.button.setIconSize(QSize(24,24))
            self.button.setText('')
            self.button.setToolTip(f'Downloads ({count} active)' if count else 'Downloads')
            return
        text='Downloads' if self.sidebar.width()>=150 else '↓'
        self.button.setText(text+(f' ({count})' if count else ''))
        self.button.setGeometry(8,max(0,self.sidebar.height()-48),max(24,self.sidebar.width()-16),40)
        self.button.raise_()
