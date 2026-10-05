import unittest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
from playlite.app import Description, horizontal_values

APP = QApplication.instance() or QApplication([])


def scroll(widget):
    event = QWheelEvent(QPointF(40, 20), QPointF(40, 20), QPoint(), QPoint(0, -120),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    APP.sendEvent(widget.viewport(), event)
    APP.processEvents()


class HiddenScrollTests(unittest.TestCase):
    def test_fade_does_not_paint_a_band_over_transparent_panel(self):
        parent = QWidget()
        parent.setStyleSheet('background: #784050;')
        layout = QVBoxLayout(parent)
        widget = Description('')
        widget.setStyleSheet('QTextBrowser { background: transparent; border: 0; }')
        widget.viewport().setAutoFillBackground(False)
        layout.addWidget(widget)
        parent.resize(400, 180)
        parent.show()
        APP.processEvents()
        widget.verticalScrollBar().setRange(0, 100)
        APP.processEvents()
        faded = parent.grab().toImage()
        widget.fades.hide()
        APP.processEvents()
        plain = parent.grab().toImage()
        self.assertEqual(faded, plain)
        parent.close()

    def test_description_retains_full_text_and_scrolls_without_visible_bar(self):
        content = 'Long description ' * 100
        widget = Description(content)
        widget.resize(240, 90)
        widget.show()
        APP.processEvents()
        self.assertEqual(widget.toPlainText(), content)
        self.assertGreater(widget.verticalScrollBar().maximum(), 0)
        scroll(widget)
        self.assertGreater(widget.verticalScrollBar().value(), 0)
        self.assertFalse(widget.verticalScrollBar().isVisible())
        widget.close()

    def test_fades_stay_at_viewport_edges_and_paint_after_scrolling(self):
        widget = Description('Long description ' * 500)
        widget.setStyleSheet('QTextBrowser { color: white; background: #1d1e20; border: 0; }')
        widget.resize(400, 180)
        widget.show()
        APP.processEvents()
        widget.verticalScrollBar().setValue(60)
        APP.processEvents()
        self.assertEqual(widget.fades.geometry(), widget.viewport().geometry())
        faded = widget.grab().toImage()
        widget.fades.hide()
        APP.processEvents()
        plain = widget.grab().toImage()
        viewport = widget.viewport().geometry()
        for first, last in [(0, 20), (viewport.height() - 20, viewport.height())]:
            differences = sum(faded.pixelColor(x + viewport.x(), y + viewport.y()) != plain.pixelColor(x + viewport.x(), y + viewport.y())
                              for y in range(first, last) for x in range(viewport.width()))
            self.assertGreater(differences, 0)
        widget.close()

    def test_description_consumes_wheel_at_both_boundaries(self):
        widget = Description('Long description ' * 100)
        widget.resize(240, 90)
        widget.show()
        APP.processEvents()
        bar = widget.verticalScrollBar()
        for position, delta in [(bar.minimum(), 120), (bar.maximum(), -120)]:
            bar.setValue(position)
            event = QWheelEvent(QPointF(40, 20), QPointF(40, 20), QPoint(), QPoint(0, delta),
                                Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                                Qt.ScrollPhase.NoScrollPhase, False)
            APP.sendEvent(widget.viewport(), event)
            self.assertTrue(event.isAccepted())
            self.assertEqual(bar.value(), position)
        widget.close()

    def test_horizontal_values_scroll_with_normal_mouse_wheel(self):
        widget = horizontal_values(['A long platform name'] * 20)
        widget.resize(200, widget.height())
        widget.show()
        APP.processEvents()
        self.assertGreater(widget.horizontalScrollBar().maximum(), 0)
        scroll(widget)
        self.assertGreater(widget.horizontalScrollBar().value(), 0)
        self.assertFalse(widget.horizontalScrollBar().isVisible())
        widget.close()
