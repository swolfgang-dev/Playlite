import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from playlite.cli import main


class CliTests(unittest.TestCase):
    def test_removed_manual_command_cannot_create_a_game(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(['--data', directory, 'manual', '--name', 'Example'])
            self.assertFalse((Path(directory) / 'library.json').exists())

    def test_core_manual_cli_has_no_plugin_specific_options(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(['--data', directory, 'manual', '--name', 'Example', '--steam-id', 'bad'])
            self.assertFalse((Path(directory) / 'library.json').exists())
