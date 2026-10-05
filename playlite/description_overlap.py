"""Remove repeated sentences from a display copy of rich description text."""
from PyQt6.QtCore import QTextBoundaryFinder
from PyQt6.QtGui import QTextCursor, QTextDocument
from .description_html import without_images


def _sentences(text):
    # Qt positions, including cursor positions, count UTF-16 code units.
    encoded = text.encode('utf-16-le')
    finder = QTextBoundaryFinder(QTextBoundaryFinder.BoundaryType.Sentence, text)
    start = 0
    while (end := finder.toNextBoundary()) != -1:
        sentence = encoded[start * 2:end * 2].decode('utf-16-le')
        if sentence.strip():
            yield start, end, ' '.join(sentence.split())
        start = end


def hide_repeated_sentences(short, full):
    """Match visible text exactly, ignoring HTML formatting and whitespace."""
    summary = QTextDocument()
    summary.setHtml(without_images(short))
    sentences = set()
    block = summary.begin()
    while block.isValid():
        sentences.update(sentence for _, _, sentence in _sentences(block.text()))
        block = block.next()
    if not sentences:
        return full
    document = QTextDocument()
    document.setHtml(without_images(full))
    removals = []
    block = document.begin()
    while block.isValid():
        parts = list(_sentences(block.text()))
        matches = [(start, end) for start, end, sentence in parts if sentence in sentences]
        if parts and len(matches) == len(parts):
            # Remove the empty paragraph too, avoiding gaps before remaining text.
            end = block.position() + block.length() - 1
            if block.next().isValid():
                end += 1
            removals.append((block.position(), end))
        else:
            removals.extend((block.position() + start, block.position() + end) for start, end in matches)
        block = block.next()
    if not removals:
        return full
    cursor = QTextCursor(document)
    for start, end in reversed(removals):
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
    return document.toHtml() if document.toPlainText().strip() else ''
