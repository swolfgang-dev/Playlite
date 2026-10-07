import signal
import unittest
from unittest.mock import patch
from playlite.process_control import terminate_processes


class StopProcesses(unittest.TestCase):
    def test_exited_or_reused_pid_is_never_signalled(self):
        with patch('playlite.process_control.alive', return_value=False), patch('playlite.process_control.os.kill') as kill:
            self.assertEqual(terminate_processes([{'pid': 123, 'start': '456'}]), 0)
            kill.assert_not_called()

    def test_unresponsive_game_escalates(self):
        with patch('playlite.process_control.alive', return_value=True), patch('playlite.process_control.os.kill') as kill:
            self.assertEqual(terminate_processes([{'pid': 123, 'start': '456'}], grace=0), 1)
            self.assertEqual(kill.call_args_list[0].args, (123, signal.SIGTERM))
            self.assertEqual(kill.call_args_list[1].args, (123, signal.SIGKILL))

    def test_pid_reused_between_snapshot_and_signal(self):
        with patch('playlite.process_control.alive', side_effect=[True, False, False, False]), patch('playlite.process_control.os.kill') as kill:
            terminate_processes([{'pid': 123, 'start': '456'}], grace=0)
            kill.assert_not_called()
