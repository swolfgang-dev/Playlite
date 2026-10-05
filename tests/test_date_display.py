import unittest
from playlite.date_display import display_date


class DateDisplayTests(unittest.TestCase):
    def test_dates_and_timestamps_share_requested_format(self):
        for value in ('2026-10-10', '2026-10-10T23:54:00-04:00', '2026-10-10 23:54', '2026-10-10T01:00:00Z'):
            self.assertEqual(display_date(value), '10-Oct-2026')
        self.assertEqual(display_date('2024-5-8'), '08-May-2024')

    def test_missing_and_invalid_dates_keep_fallback(self):
        self.assertEqual(display_date(None, 'Unknown'), 'Unknown')
        self.assertEqual(display_date('', 'Never'), 'Never')
        self.assertEqual(display_date('Invalid date'), 'Invalid date')

    def test_metadata_preview_uses_same_format(self):
        from playlite.metadata_dialog import display
        self.assertEqual(display({'ReleaseDate': '2026-10-10'}), '10-Oct-2026')
