from plugin_test_support import require_plugin
require_plugin('SteamMetadata')
import unittest
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QTextDocument
from PyQt6.QtWidgets import QApplication
from playlite.rich_description import FullDescription, CollapsibleDescription
from playlite_plugins.steammetadata.metadata import normalize
from playlite.description_html import without_images

APP = QApplication.instance() or QApplication([])


class FullDescriptionTests(unittest.TestCase):
    def test_wheel_passes_through_at_edges_and_scrolls_back_into_description(self):
        from PyQt6.QtCore import QPoint, QPointF, Qt
        from PyQt6.QtGui import QWheelEvent
        widget = CollapsibleDescription('<p>' + 'Long text ' * 500 + '</p>')
        widget.resize(400, 200)
        widget.show()
        for _ in range(5):
            APP.processEvents()
        viewer = widget.description
        bar = viewer.verticalScrollBar()
        self.assertGreater(bar.maximum(), bar.minimum())
        def wheel(delta, pixels=False):
            event = QWheelEvent(QPointF(20, 20), QPointF(20, 20),
                                QPoint(0, delta) if pixels else QPoint(),
                                QPoint() if pixels else QPoint(0, delta),
                                Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                                Qt.ScrollPhase.NoScrollPhase, False)
            viewer.wheelEvent(event)
            return event.isAccepted()
        for pixels in (False, True):
            bar.setValue(bar.minimum())
            self.assertFalse(wheel(120, pixels))
            self.assertTrue(wheel(-120, pixels))
            self.assertGreater(bar.value(), bar.minimum())
            bar.setValue(bar.maximum())
            self.assertFalse(wheel(-120, pixels))
            self.assertTrue(wheel(120, pixels))
            self.assertLess(bar.value(), bar.maximum())
        viewer.scrollable = False
        self.assertFalse(wheel(120))
        widget.close()

    def test_steam_keeps_short_and_full_descriptions_separate_without_images(self):
        html = '<h2>Story</h2><p>Text &amp; more</p><img src="https://shared.fastly.steamstatic.com/story.jpg">'
        fields = normalize(42, {'short_description': 'Summary', 'about_the_game': html,
                                'detailed_description': 'Promotion' + html})['fields']
        self.assertEqual(fields['Description'], 'Summary')
        self.assertEqual(fields['FullDescription'], '<h2>Story</h2><p>Text &amp; more</p>')
        self.assertEqual(without_images('<p>Text</p><IMG src="a>b"/><img src="two">'), '<p>Text</p>')
        self.assertNotIn('FullDescription', normalize(42, {'short_description': 'Summary'})['fields'])

    def test_collapsed_by_default_and_toggle_restores_truncation(self):
        widget = CollapsibleDescription('<p>' + 'Long text ' * 500 + '</p>')
        widget.resize(400, 200)
        widget.show()
        for _ in range(5):
            APP.processEvents()
        viewer = widget.description
        self.assertFalse(viewer.expanded)
        self.assertEqual(viewer.height(), viewer.collapsed_height)
        self.assertTrue(widget.toggle.isHidden())
        from PyQt6.QtWidgets import QFrame
        from PyQt6.QtCore import QPoint, QPointF, Qt
        from PyQt6.QtGui import QWheelEvent
        self.assertEqual(viewer.frameShape(), QFrame.Shape.NoFrame)
        wheel = QWheelEvent(QPointF(20, 20), QPointF(20, 20), QPoint(), QPoint(0, -120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        fade_position = viewer.fades.geometry()
        viewer.wheelEvent(wheel)
        APP.processEvents()
        self.assertEqual(viewer.fades.geometry(), fade_position)
        self.assertEqual(viewer.fades.parentWidget(), viewer)
        self.assertGreater(viewer.verticalScrollBar().value(), 0)
        self.assertTrue(wheel.isAccepted())
        from playlite.scroll_fades import ScrollFades
        self.assertIsInstance(viewer.fades, ScrollFades)
        self.assertFalse(viewer.fades.horizontal)
        self.assertEqual(viewer.objectName(), 'description')
        self.assertTrue(viewer.fades.isVisible())
        self.assertTrue(widget.toggle.isHidden())
        from PyQt6.QtTest import QTest
        QTest.mouseClick(viewer.viewport(), Qt.MouseButton.LeftButton)
        self.assertTrue(viewer.animating)
        QTest.qWait(400)
        for _ in range(5):
            APP.processEvents()
        self.assertTrue(viewer.expanded)
        self.assertGreater(viewer.height(), viewer.collapsed_height)
        self.assertGreater(viewer.verticalScrollBar().maximum(), 0)
        self.assertEqual(widget.toggle.text(), 'Hide')
        widget.toggle.click()
        self.assertFalse(widget.toggle.isHidden())
        QTest.qWait(400)
        APP.processEvents()
        self.assertEqual(viewer.height(), viewer.collapsed_height)
        self.assertEqual(viewer.verticalScrollBar().value(), 0)
        self.assertTrue(widget.toggle.isHidden())
        widget.close()

    def test_expanding_can_reveal_panel_in_outer_page(self):
        from PyQt6.QtWidgets import QScrollArea, QWidget, QVBoxLayout
        from PyQt6.QtCore import QTimer, QPoint
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        layout = QVBoxLayout(page)
        spacer = QWidget()
        spacer.setFixedHeight(500)
        layout.addWidget(spacer)
        panel = CollapsibleDescription('<p>' + 'Text ' * 1000 + '</p>')
        layout.addWidget(panel)
        scroll.setWidget(page)
        scroll.resize(500, 700)
        scroll.show()
        for _ in range(5):
            APP.processEvents()
        scroll.ensureWidgetVisible(panel.description, 0, 24)
        original = scroll.verticalScrollBar().value()
        panel.open_panel()
        from PyQt6.QtTest import QTest
        QTest.qWait(150)
        self.assertTrue(panel.description.animating)
        self.assertGreater(panel.description.height(), panel.description.collapsed_height)
        self.assertLess(panel.description.height(), panel.description.expanded_height)
        self.assertGreater(scroll.verticalScrollBar().value(), original)
        QTest.qWait(300)
        for _ in range(8):
            APP.processEvents()
        self.assertGreater(scroll.verticalScrollBar().value(), original)
        bottom = panel.toggle.mapTo(scroll.viewport(), QPoint(0, panel.toggle.height())).y()
        self.assertLessEqual(bottom, scroll.viewport().height())
        opened_position = scroll.verticalScrollBar().value()
        panel.toggle.click()
        self.assertFalse(panel.toggle.isHidden())
        QTest.qWait(150)
        self.assertTrue(panel.description.animating)
        self.assertGreater(panel.description.height(), panel.description.collapsed_height)
        self.assertLess(scroll.verticalScrollBar().value(), opened_position)
        QTest.qWait(300)
        self.assertTrue(panel.toggle.isHidden())
        self.assertEqual(panel.description.height(), panel.description.collapsed_height)
        scroll.close()

    def test_existing_saved_description_images_are_not_rendered(self):
        widget = FullDescription('<p>Text</p><img src="https://shared.fastly.steamstatic.com/a.png">')
        self.assertNotIn('<img', widget.toHtml())
        self.assertIsNone(widget.loadResource(QTextDocument.ResourceType.ImageResource, QUrl('file:///etc/passwd')))
        widget.close()

    def test_short_description_does_not_need_toggle(self):
        widget = CollapsibleDescription('Short text')
        widget.resize(600, 200)
        widget.show()
        for _ in range(5):
            APP.processEvents()
        self.assertTrue(widget.toggle.isHidden())
        widget.close()
