import unittest
from unittest.mock import patch
from playlite.desktop import open_folder


class DesktopTests(unittest.TestCase):
    def test_repo_folder_launch_restores_host_configuration(self):
        environment = {'PLAYLITE_PROFILE': 'repo', 'HOME': '/repo/home',
                       'PLAYLITE_HOST_HOME': '/home/user', 'XDG_CONFIG_HOME': '/repo/config',
                       'PLAYLITE_HOST_XDG_CONFIG_HOME': '/host/config',
                       'XDG_DATA_HOME': '/repo/data', 'DISPLAY': ':0'}
        with patch.dict('os.environ', environment, clear=True), patch('playlite.desktop.subprocess.Popen') as launch:
            open_folder('/games/Example Game')
        args, kwargs = launch.call_args
        self.assertEqual(args[0], ['xdg-open', '/games/Example Game'])
        self.assertEqual(kwargs['env']['HOME'], '/home/user')
        self.assertEqual(kwargs['env']['XDG_CONFIG_HOME'], '/host/config')
        self.assertNotIn('XDG_DATA_HOME', kwargs['env'])
        self.assertEqual(kwargs['env']['DISPLAY'], ':0')

    def test_installed_profile_keeps_desktop_environment(self):
        environment = {'HOME': '/home/user', 'XDG_CONFIG_HOME': '/custom/config'}
        with patch.dict('os.environ', environment, clear=True), patch('playlite.desktop.subprocess.Popen') as launch:
            open_folder('/games')
        self.assertEqual(launch.call_args.kwargs['env'], environment)
