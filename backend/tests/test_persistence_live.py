"""Isolated fixtures only; never insert synthetic observations into the live DB."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import sqlite3
import unittest
from unittest.mock import patch

from backend.persistence_live import persistence_live
from backend.tests.support import fixture, http_server, request, test_settings, validated

NOW = datetime(2026, 11, 12, 1, 0, tzinfo=timezone.utc)


def snapshot(occupied=3):
    return [{'slot_id': f'P{i}', 'device_id': f'esp32_{(i-1)//4+1:02d}',
        'occupancy_status': 'OCCUPIED' if i <= occupied else 'VACANT',
        'distance_cm': 10 if i <= occupied else 100,
        'received_at': NOW.isoformat(), 'measured_at': NOW.isoformat(),
        'sequence': 1, 'observed': True, 'stale': False} for i in range(1, 13)]


class PersistenceAdapterTests(unittest.TestCase):
    def test_exact_rule_agrees_with_existing_parameter_free_estimator_for_all_counts(self):
        import numpy as np
        from ml.phase4_models import PersistenceRegressor
        for count in range(13):
            # Only actual fixture slot states and their total, not padded ML lags.
            x = np.array([[*(int(i < count) for i in range(12)), count]])
            expected = PersistenceRegressor().predict(x)[0]
            result = persistence_live(snapshot(count), now=NOW)
            self.assertTrue(result.available)
            self.assertEqual(result.predicted_occupied, expected)
            self.assertEqual(result.target_timestamp, NOW + timedelta(minutes=15))
            self.assertEqual(result.prediction_timestamp, NOW)

    def test_missing_duplicate_wrong_device_and_unexpected_slots_block(self):
        variants = [snapshot()[:-1], snapshot()+[snapshot()[0]]]
        for field, value in [('device_id', 'esp32_03'), ('slot_id', 'P99')]:
            rows = snapshot(); rows[0][field] = value; variants.append(rows)
        for rows in variants:
            result = persistence_live(rows, now=NOW)
            self.assertFalse(result.available)
            self.assertTrue(result.blockers)
            self.assertIsNone(result.predicted_occupied)
            self.assertIsNone(result.current_occupied)

    def test_stale_unknown_unobserved_or_invalid_distance_block(self):
        for field, value in [('stale', True), ('observed', False), ('occupancy_status', 'UNKNOWN'),
                             ('distance_cm', None), ('distance_cm', float('nan')), ('distance_cm', 401)]:
            rows = snapshot(); rows[0][field] = value
            self.assertFalse(persistence_live(rows, now=NOW).available)

    def test_receipt_and_measurement_missing_old_future_naive_invalid_block(self):
        for field in ['received_at', 'measured_at']:
            for value in [None, (NOW-timedelta(seconds=31)).isoformat(),
                          (NOW+timedelta(seconds=3)).isoformat(), '2026-11-12T01:00:00', 'invalid']:
                rows = snapshot(); rows[0][field] = value
                result = persistence_live(rows, now=NOW)
                self.assertFalse(result.available, (field, value))
                self.assertIsNone(result.prediction_timestamp)

    def test_freshness_ceiling_cannot_be_weakened_and_stricter_setting_applies(self):
        rows = snapshot(); rows[0]['received_at'] = (NOW-timedelta(seconds=31)).isoformat()
        self.assertFalse(persistence_live(rows, stale_seconds=300, now=NOW).available)
        rows[0]['received_at'] = (NOW-timedelta(seconds=11)).isoformat()
        self.assertFalse(persistence_live(rows, stale_seconds=10, now=NOW).available)
        rows[0]['received_at'] = (NOW-timedelta(seconds=30)).isoformat()
        self.assertTrue(persistence_live(rows, now=NOW).available)

    def test_no_input_mutation(self):
        rows = snapshot(); before = deepcopy(rows)
        persistence_live(rows, now=NOW)
        self.assertEqual(rows, before)


class PersistenceEndpointTests(unittest.TestCase):
    def test_real_http_and_isolated_sqlite_success_and_unavailable_are_read_only(self):
        with test_settings() as settings, http_server(settings) as (app, base):
            status, missing = request(base, '/predictions/persistence-live')
            self.assertEqual(status, 200)
            self.assertFalse(missing['available'])
            self.assertEqual(len(missing['blockers']), 12)
            for board in range(1, 4): app.state.database.persist(validated(fixture(board)))
            before = app.state.database.history()['total']
            status, valid = request(base, '/predictions/persistence-live')
            self.assertEqual(status, 200)
            self.assertTrue(valid['available'])
            self.assertEqual(valid['current_occupied'], 0)
            self.assertEqual(valid['predicted_occupied'], 0)
            self.assertEqual(app.state.database.history()['total'], before)
            self.assertIn('/predictions/persistence-live', request(base, '/openapi.json')[1]['paths'])

    def test_database_failure_uses_existing_safe_503_handler(self):
        with test_settings() as settings, http_server(settings) as (app, base):
            with patch.object(app.state.database, 'current', side_effect=sqlite3.OperationalError('private-path')):
                status, value = request(base, '/predictions/persistence-live')
                self.assertEqual(status, 503)
                self.assertNotIn('private', str(value))
