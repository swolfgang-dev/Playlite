"""Regression coverage for removal of independent Manual launching."""
from importlib.util import find_spec
from tempfile import TemporaryDirectory
import unittest
from playlite.providers import discover_plugins, installation_methods


class RemovedManualTests(unittest.TestCase):
    def test_manual_is_not_an_installation_or_launch_provider(self):
        with TemporaryDirectory() as folder:
            self.assertNotIn('Manual', discover_plugins(folder))
        self.assertNotIn('Manual', installation_methods({}))
        self.assertIsNone(find_spec('playlite.manual_launch'))
        self.assertIsNone(find_spec('playlite.manual_installation'))
