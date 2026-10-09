from .theme import set_style
"""Artwork preview cards for the image editor."""
from pathlib import Path
from tempfile import TemporaryDirectory
import urllib.parse
import urllib.request
from PyQt6.QtCore import Qt, QUrl, QEvent
from PyQt6.QtGui import QDesktopServices, QImageReader, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QSizePolicy, QWidget, QGridLayout
from .lifecycle import choose_file, ask_text
from .metadata_dialog import Task
from PyQt6.QtCore import QThreadPool


class MediaCard(QFrame):
    def __init__(self, title, value, editor, preview_height):
        super().__init__()
        self.editor = editor
        self.title = title
        self.setObjectName('mediaCard')
        set_style(self, 'QFrame#mediaCard { background: #1d1e20; border-radius: 12px; }')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        heading = QLabel(title)
        set_style(heading, 'font-weight: bold;')
        layout.addWidget(heading)
        actions = QHBoxLayout()
        self.actions = actions
        actions.setSpacing(8)
        for text, tooltip, handler in [('+', 'Choose image file', self.browse),
                                        ('↗', 'Download image from URL', self.from_url),
                                        ('×', 'Remove image', self.clear),
                                        ('◎', 'Search for images in browser', self.search)]:
            button = QPushButton(text)
            button.setToolTip(tooltip)
            button.setFixedSize(40, 34)
            set_style(button, 'padding: 0; font-size: 20px;')
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.dimensions = QLabel()
        layout.addWidget(self.dimensions)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight({'Cover': 280, 'Icon': 112, 'Header': 112, 'Background': 176}.get(title,112))
        self.preview.setMaximumHeight(preview_height)
        self.preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.preview.installEventFilter(self)
        self.source_pixmap = QPixmap()
        layout.addWidget(self.preview, 1)
        self.path = QLineEdit(value)
        self.path.hide()
        layout.addWidget(self.path)
        self.path.textChanged.connect(self.update_preview)
        self.update_preview()

    def update_preview(self):
        pixmap = QPixmap(self.path.text())
        self.source_pixmap = pixmap
        self.preview.clear()
        if pixmap.isNull():
            self.dimensions.setText('No image')
        else:
            self.dimensions.setText(f'{pixmap.width()}×{pixmap.height()}px')
            self.scale_preview()
        self.preview.setToolTip(self.path.text())

    def scale_preview(self):
        if not self.source_pixmap.isNull():
            self.preview.setPixmap(self.source_pixmap.scaled(
                max(1, self.preview.width()), max(1, self.preview.height()),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def eventFilter(self, watched, event):
        if watched is self.preview and event.type() == QEvent.Type.Resize:
            self.scale_preview()
        return super().eventFilter(watched, event)

    def browse(self):
        filename, _ = choose_file(self.editor, f'Choose {self.title.lower()}', '', 'Images (*.png *.jpg *.jpeg *.webp *.bmp *.ico)')
        if filename:
            self.path.setText(filename)

    def clear(self):
        self.path.clear()

    def search(self):
        query = self.editor.fields['Name'].text() + ' ' + self.title
        QDesktopServices.openUrl(QUrl('https://www.google.com/search?tbm=isch&q=' + urllib.parse.quote(query)))

    def from_url(self):
        url, accepted = ask_text(self.editor, 'Image URL', 'Direct HTTPS image URL')
        if not accepted or not url.strip():
            return
        parsed = urllib.parse.urlsplit(url.strip())
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            self.editor.error.setText('Enter a direct HTTPS image URL.')
            return
        cache = TemporaryDirectory(prefix='playlite-image-')
        self.editor.download_caches.append(cache)
        target = Path(cache.name) / 'image.png'
        def fetch():
            with urllib.request.urlopen(url.strip(), timeout=20) as response:
                content = response.read(20 * 1024 * 1024 + 1)
            if len(content) > 20 * 1024 * 1024:
                raise ValueError('Image is too large (maximum 20 MB).')
            target.write_bytes(content)
            if not QImageReader(str(target)).canRead():
                raise ValueError('The URL did not return a readable image.')
            return str(target)
        self.task = Task(fetch)
        self.task.signals.succeeded.connect(self.path.setText)
        self.task.signals.failed.connect(lambda error: self.editor.error.setText('Could not download image. Check the URL and try again.'))
        self.editor.error.setText('Downloading image…')
        QThreadPool.globalInstance().start(self.task)


class ArtworkGrid(QWidget):
    """Reflow artwork cards without squeezing their preview areas to tiny strips."""
    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Maximum)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0,0,0,0)
        self.grid.setSpacing(16)
        self.cards = {}
        self.columns = None

    def set_cards(self, cards):
        self.cards = cards
        self.arrange()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.arrange()

    def arrange(self):
        if not self.cards:return
        columns = 3 if self.width() >= 820 else 2 if self.width() >= 540 else 1
        if columns == self.columns:return
        self.columns = columns
        for card in self.cards.values():self.grid.removeWidget(card)
        for column in range(3):self.grid.setColumnStretch(column,1 if column < columns else 0)
        for row in range(4):self.grid.setRowStretch(row,0)
        if columns == 3:
            positions = [('CoverImage',0,0,2,1),('Icon',0,1,1,1),('HeaderImage',0,2,1,1),('BackgroundImage',1,1,1,2)]
        elif columns == 2:
            positions = [('CoverImage',0,0,2,1),('Icon',0,1,1,1),('HeaderImage',1,1,1,1),('BackgroundImage',2,0,1,2)]
        else:
            positions = [(key,row,0,1,1) for row,key in enumerate(('CoverImage','Icon','HeaderImage','BackgroundImage'))]
        for key,row,column,rows,cols in positions:self.grid.addWidget(self.cards[key],row,column,rows,cols)
