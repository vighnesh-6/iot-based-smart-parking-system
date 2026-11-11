"""Regression checks for sparse receipt-time history; fixtures are not telemetry."""
from datetime import timedelta
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from dashboard.data_views import minute_history, slot_history


ORIGIN = pd.Timestamp('2026-11-11T15:13:02.693Z')


def fixture(identity, seconds=0, state='VACANT', applied=1):
    return {'id': identity, 'slot_id': 'P3', 'received_at': (ORIGIN + timedelta(seconds=seconds)).isoformat(),
            'occupancy_status': state, 'applied_current': applied}


class SparseHistoryTests(unittest.TestCase):
    def test_recent_receipts_cannot_hide_old_or_future_measurements(self):
        from dashboard.data_views import slot_snapshot
        from test_dashboard import slots, NOW
        payload = slots()
        payload[0]['measured_at'] = (NOW - timedelta(seconds=38)).isoformat()
        payload[1]['measured_at'] = (NOW + timedelta(seconds=10)).isoformat()
        payload[2]['measured_at'] = NOW.isoformat()
        snapshot, counts = slot_snapshot(payload, 30, NOW)
        self.assertEqual(counts['unknown'], 2)
        self.assertEqual(snapshot[0]['display_status'], 'UNKNOWN')
        self.assertEqual(snapshot[1]['display_status'], 'UNKNOWN')
        self.assertEqual(snapshot[2]['display_status'], 'OCCUPIED')
        self.assertIn('unavailable', snapshot[3]['reason'])

    def test_original_twenty_two_event_failure_is_fixed_without_changing_minutes(self):
        items = [fixture(i, i / 2000) for i in range(22)]
        start, end = ORIGIN.floor('min'), ORIGIN.ceil('min')
        self.assertEqual(minute_history(items, start, end, 30).P3.notna().sum(), 0)
        actual = slot_history(items, 'P3', start, end, 30)
        self.assertEqual(actual.P3.notna().sum(), 22)
        self.assertEqual(actual.timestamp.dt.tz_convert('UTC').iloc[0], ORIGIN)

    def test_unknown_and_long_gaps_break_lines_and_partial_slots_remain_visible(self):
        items = [fixture(1), fixture(2, 5, 'UNKNOWN'), fixture(3, 10, 'OCCUPIED'), fixture(4, 100)]
        frame = slot_history(items, 'P3', ORIGIN, ORIGIN + timedelta(minutes=2), 30)
        self.assertEqual(frame.P3.notna().sum(), 3)
        self.assertTrue(np.isnan(frame.P3.iloc[1]))
        self.assertTrue(np.isnan(frame.P3.iloc[3]))
        self.assertTrue(pd.isna(frame.observation_id.iloc[3]))

    def test_filter_boundaries_and_history_only(self):
        frame = slot_history([fixture(1, -1), fixture(2), fixture(3, 1, applied=0), fixture(4, 3)],
                             'P3', ORIGIN, ORIGIN + timedelta(seconds=2), 30)
        self.assertEqual(frame.observation_id.tolist(), [2])
        self.assertTrue(slot_history([], 'P3', ORIGIN, ORIGIN, 30).empty)

    def test_invalid_timezone_and_duplicate_records_are_rejected(self):
        for items in [[fixture(1), fixture(1)], [{**fixture(1), 'received_at': '2026-11-11T15:13:02'}]]:
            with self.assertRaises(ValueError): slot_history(items, 'P3', ORIGIN, ORIGIN, 30)

    def test_single_observation_uses_markers_and_real_receipt_axis(self):
        from dashboard.app import draw_history
        frame = slot_history([fixture(1)], 'P3', ORIGIN, ORIGIN, 30)
        with patch('dashboard.app.st.plotly_chart') as chart:
            draw_history(frame, 'P3')
        figure = chart.call_args.args[0]
        self.assertEqual(figure.data[0].mode, 'lines+markers')
        self.assertFalse(figure.data[0].connectgaps)
        self.assertEqual(list(figure.data[0].y), [0.0])
        self.assertIn('receipt', figure.layout.xaxis.title.text)


if __name__ == '__main__':
    unittest.main()
