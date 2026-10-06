import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication, QDialog
from playlite.manual_installation import ManualInstallation
from playlite.plugin_fields import validate_declarations

APP = QApplication.instance() or QApplication([])


class DeclaredFieldTests(unittest.TestCase):
    def test_absent_plugins_preserve_their_data_without_adding_controls(self):
        with TemporaryDirectory() as temporary, patch('playlite.providers.discover_plugins', return_value={}):
            editor = QDialog(); editor.data = Path(temporary); editor.fields = {}
            game = {'Name': 'Example', 'MetadataIds': {'ExampleSource': '123'}, 'ExternalId': '456'}
            widget = ManualInstallation().create_editor(editor, game)
            self.assertNotIn('ExternalId', widget.fields)
            result = ManualInstallation().collect(widget, game)
            self.assertEqual(result['ExternalId'], '456')
            self.assertEqual(result['MetadataIds'], {'ExampleSource': '123'})

    def test_plugin_declares_validates_and_clears_its_metadata_id(self):
        plugin = SimpleNamespace(game_fields=[{'key': 'ExternalId', 'label': 'External ID',
            'metadata_provider': 'ExampleSource', 'positive_id': True}])
        with TemporaryDirectory() as temporary, patch('playlite.providers.discover_plugins', return_value={'Example': plugin}):
            editor = QDialog(); editor.data = Path(temporary); editor.fields = {}
            game = {'Name': 'Example', 'MetadataIds': {'ExampleSource': '123', 'Other': 'kept'}}
            widget = ManualInstallation().create_editor(editor, game)
            field = widget.fields['ExternalId']
            self.assertEqual(field.text(), '123')
            field.setText('-1')
            with self.assertRaises(ValueError):
                ManualInstallation().collect(widget, game)
            field.clear()
            self.assertEqual(ManualInstallation().collect(widget, game)['MetadataIds'], {'Other': 'kept'})

    def test_invalid_manifest_declarations_are_rejected(self):
        for fields in ({}, [None], [{'key': 'Id'}], [{'key': 'Id', 'label': 'ID', 'positive_id': 'yes'}]):
            with self.assertRaises(ValueError):
                validate_declarations(fields)
