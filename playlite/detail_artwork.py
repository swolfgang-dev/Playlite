"""Decode and resize detail artwork on worker threads; QPixmap stays on the UI thread."""
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QImage,QImageReader


def read(source, target):
    if not source:return QImage()
    reader=QImageReader(source);reader.setAutoTransform(True)
    size=reader.size()
    if size.isValid():reader.setScaledSize(size.scaled(target,Qt.AspectRatioMode.KeepAspectRatio))
    return reader.read()


def load(header, cover, ratio):
    return (read(header,QSize(round(1600*ratio),round(1000*ratio))),
            read(cover,QSize(round(190*ratio),round(295*ratio))))
