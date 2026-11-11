"""Isolated fixtures only: never publish MQTT or write a live database."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import numpy as np
import pandas as pd

from dashboard.api_client import ApiClient, ApiError, HistoryResult
from dashboard.config import ROOT, Settings
from dashboard.data_views import live_feature_record, minute_history, slot_snapshot
from dashboard.prediction import PredictionError, predict, read_results, synthetic_example
from ml.features import FEATURE_COLUMNS, engineer_features
from ml.generate_data import SLOTS, TIMEZONE

NOW = datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc)


def slots(now=NOW):
    return [{'slot_id': f'P{i}', 'device_id': f'esp32_{(i-1)//4+1:02d}',
        'occupancy_status': 'OCCUPIED' if i <= 3 else 'VACANT',
        'distance_cm': 10.0 if i <= 3 else 100.0, 'received_at': now.isoformat(),
        'measured_at': None, 'sequence': 1, 'stale': False, 'observed': True} for i in range(1, 13)]


def observations(now=NOW):
    return [{'id': i, 'slot_id': f'P{i}', 'received_at': now.isoformat(),
             'occupancy_status': 'OCCUPIED' if i <= 3 else 'VACANT', 'applied_current': 1}
            for i in range(1, 13)]


class ConfigTests(unittest.TestCase):
    def test_environment_overrides_toml_and_paths_are_portable(self):
        with patch.dict(os.environ, {'DASHBOARD_CONFIG': 'dashboard/config.example.toml',
                                    'API_BASE_URL': 'https://example.invalid/api', 'REFRESH_SECONDS': '15'}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.api_base_url, 'https://example.invalid/api')
        self.assertEqual(settings.refresh_seconds, 15)
        self.assertTrue(settings.model_path.is_file())

    def test_defaults_do_not_depend_on_working_directory(self):
        before = Path.cwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                with patch.dict(os.environ, {}, clear=True): settings = Settings.from_env()
                self.assertEqual(settings.results_path, ROOT/'ml/artifacts/phase4/model_results.json')
            finally: os.chdir(before)

    def test_invalid_configuration_rejected(self):
        for values in ({'api_base_url': 'file:///x'}, {'api_base_url': 'https://user:secret@example.invalid'},
                       {'api_base_url': 'https://example.invalid/?token=x'}, {'prediction_adapter': 'other'},
                       {'timeout_seconds': 0}, {'refresh_seconds': 12}, {'history_max_rows': 0}):
            with self.subTest(values=values), self.assertRaises(ValueError): Settings(**values)


class ApiTests(unittest.TestCase):
    def test_client_uses_configured_url_get_timeout_and_query(self):
        with patch('dashboard.api_client.urlopen', return_value=io.BytesIO(b'[]')) as opening:
            result = ApiClient(Settings(api_base_url='https://example.invalid/api')).get('/history', params={'slot_id': 'P1'})
        request = opening.call_args.args[0]
        self.assertEqual(request.full_url, 'https://example.invalid/api/history?slot_id=P1')
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(opening.call_args.kwargs['timeout'], 3)
        self.assertEqual(result, [])

    def test_unreachable_timeout_invalid_json_and_http_errors(self):
        client = ApiClient(Settings())
        for error in (URLError('private diagnostic'), TimeoutError(), HTTPError('url', 500, 'private', {}, None)):
            with patch('dashboard.api_client.urlopen', side_effect=error), self.assertRaises(ApiError): client.get('/slots')
        with patch('dashboard.api_client.urlopen', return_value=io.BytesIO(b'not json')), self.assertRaises(ApiError): client.get('/slots')

    def test_degraded_health_503_is_readable(self):
        response = HTTPError('url', 503, 'degraded', {}, io.BytesIO(b'{"status":"degraded"}'))
        with patch('dashboard.api_client.urlopen', side_effect=response):
            self.assertEqual(ApiClient(Settings()).get('/health', degraded_health=True)['status'], 'degraded')

    def test_only_supported_read_only_endpoints(self):
        with self.assertRaises(ValueError): ApiClient(Settings()).get('/delete')

    def test_optional_gateway_token_is_a_header_and_not_configuration_repr(self):
        settings = Settings(api_bearer_token='test-fixture-token')
        with patch('dashboard.api_client.urlopen', return_value=io.BytesIO(b'[]')) as opening:
            ApiClient(settings).get('/slots')
        self.assertEqual(opening.call_args.args[0].get_header('Authorization'), 'Bearer test-fixture-token')
        self.assertNotIn('test-fixture-token', repr(settings))

    def test_bounded_pagination_reports_truncation(self):
        client = ApiClient(Settings(history_max_rows=12))
        with patch.object(client, 'get', return_value={'items': list(range(12)), 'total': 100, 'offset': 0, 'limit': 12}):
            result = client.history(since='start', until='end')
        self.assertTrue(result.truncated)
        self.assertEqual(len(result.items), 12)

    def test_complete_pagination_preserves_upper_time_bound(self):
        client = ApiClient(Settings(history_max_rows=2000))
        pages = [{'items': list(range(1000)), 'total': 1001, 'offset': 0, 'limit': 1000},
                 {'items': [1000], 'total': 1001, 'offset': 1000, 'limit': 1000}]
        with patch.object(client, 'get', side_effect=pages) as getting:
            result = client.history(since='start', until='fixed')
        self.assertFalse(result.truncated)
        self.assertEqual(len(result.items), 1001)
        self.assertEqual([call.kwargs['params']['until'] for call in getting.call_args_list], ['fixed', 'fixed'])

    def test_inconsistent_pages_are_rejected(self):
        client = ApiClient(Settings())
        for page in ({'items': [], 'total': 3, 'offset': 0, 'limit': 1000},
                     {'items': [], 'total': -1, 'offset': 0, 'limit': 1000}, {'bad': True}):
            with patch.object(client, 'get', return_value=page), self.assertRaises(ApiError):
                client.history(since='start', until='end')


class ViewTests(unittest.TestCase):
    def test_twelve_slots_counts_and_numeric_order(self):
        snapshot, counts = slot_snapshot(list(reversed(slots())), 30, NOW)
        self.assertEqual([s['slot_id'] for s in snapshot], list(SLOTS))
        self.assertEqual((counts['occupied'], counts['vacant'], counts['unknown']), (3, 9, 0))

    def test_unseen_stale_unknown_and_future_receipts_are_not_vacant(self):
        payload = slots()
        payload[0].update(observed=False, received_at=None)
        payload[1]['received_at'] = (NOW-timedelta(seconds=31)).isoformat()
        payload[2].update(occupancy_status='UNKNOWN', distance_cm=None)
        payload[3]['received_at'] = (NOW+timedelta(seconds=10)).isoformat()
        snapshot, counts = slot_snapshot(payload, 30, NOW)
        self.assertEqual(counts['unknown'], 4)
        self.assertEqual(counts['vacant'], 8)
        self.assertTrue(all(s['display_status']=='UNKNOWN' for s in snapshot[:4]))

    def test_backend_stale_flag_is_never_overridden(self):
        payload = slots(); payload[0]['stale'] = True
        _, counts = slot_snapshot(payload, 30, NOW)
        self.assertEqual(counts['unknown'], 1)

    def test_invalid_snapshot_identity_distance_and_missing_slots(self):
        for field, value in (('slot_id', 'P13'), ('device_id', 'esp32_03'), ('distance_cm', float('nan'))):
            payload = slots(); payload[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): slot_snapshot(payload, 30, NOW)
        with self.assertRaises(ValueError): slot_snapshot(slots()[:-1], 30, NOW)

    def test_minute_asof_never_uses_future_or_expired_readings(self):
        frame = minute_history(observations(), NOW-timedelta(minutes=1), NOW+timedelta(minutes=1), 30)
        self.assertTrue(np.isnan(frame.total_occupied.iloc[0]))
        self.assertEqual(frame.total_occupied.iloc[1], 3)
        self.assertTrue(np.isnan(frame.total_occupied.iloc[2]))

    def test_history_only_unknown_and_partial_coverage_produce_gaps(self):
        items = observations(); items[0]['applied_current'] = 0
        items[1]['occupancy_status'] = 'UNKNOWN'
        frame = minute_history(items, NOW, NOW, 30)
        self.assertEqual(frame.known_slots.iloc[0], 10)
        self.assertTrue(np.isnan(frame.total_occupied.iloc[0]))

    def test_future_intervention_does_not_change_history(self):
        original = minute_history(observations(), NOW, NOW, 30)
        future = observations(NOW+timedelta(seconds=1))
        for row in future: row['id'] += 12; row['occupancy_status'] = 'VACANT'
        modified = minute_history(observations()+future, NOW, NOW, 30)
        pd.testing.assert_frame_equal(original, modified)

    def test_empty_and_invalid_history(self):
        frame = minute_history([], NOW, NOW, 30)
        self.assertEqual(frame.known_slots.iloc[0], 0)
        with self.assertRaises(ValueError): minute_history([{'id': 1}], NOW, NOW, 30)
        duplicated = observations()+observations()
        with self.assertRaises(ValueError): minute_history(duplicated, NOW, NOW, 30)

    def test_live_features_reuse_frozen_pipeline_and_reject_gaps(self):
        timeline = pd.date_range('2026-09-14', periods=10081, freq='min', tz=TIMEZONE)
        frame = pd.DataFrame({'timestamp': timeline, 'data_source': 'api_telemetry'})
        for i, slot in enumerate(SLOTS): frame[slot] = (np.arange(len(frame))//(i+13)) % 2
        frame['total_occupied'] = frame[list(SLOTS)].sum(axis=1)
        actual = live_feature_record(frame)
        raw = frame.copy(); changes = raw[list(SLOTS)].diff()
        raw['arrivals'] = changes.eq(1).sum(axis=1); raw['departures'] = changes.eq(-1).sum(axis=1)
        expected = engineer_features(raw).loc[:, list(FEATURE_COLUMNS)].iloc[-1]
        np.testing.assert_allclose(list(actual.values()), expected.to_numpy(), rtol=0, atol=0)
        frame.loc[500, 'P1'] = np.nan
        with self.assertRaises(ValueError): live_feature_record(frame)
        with self.assertRaises(ValueError): live_feature_record(frame.iloc[:20])


class PredictionTests(unittest.TestCase):
    def test_invalid_adapter_worker_and_response_fail_safely(self):
        with self.assertRaises(PredictionError): predict({}, Settings(prediction_adapter='subprocess'))
        with patch('dashboard.prediction._in_process', return_value={'predictions': [13], 'selected_model': 'persistence', 'horizon_minutes': 15}):
            with self.assertRaises(PredictionError): predict({}, Settings())

    def test_model_metrics_are_frozen_synthetic_results(self):
        result = read_results(Settings())
        self.assertEqual(result['selected_model'], 'persistence')
        self.assertAlmostEqual(result['test']['persistence']['clipped']['mae'], .30771412365286444)

    def test_both_native_adapters_reload_and_predict_identically(self):
        interpreter = os.environ.get('PHASE5_TEST_ML_PYTHON')
        if not interpreter:
            self.skipTest('Set PHASE5_TEST_ML_PYTHON to the approved native ML interpreter')
        settings = Settings(prediction_adapter='subprocess', ml_python=interpreter)
        worker = synthetic_example(settings)
        process = subprocess.run([interpreter, '-B', '-c',
            'import json; from dashboard.config import Settings; from dashboard.prediction import synthetic_example; print(json.dumps(synthetic_example(Settings())))'],
            cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        native = json.loads(process.stdout)
        self.assertEqual(worker, native)
        self.assertEqual(native['observation_source'], 'synthetic')
        self.assertTrue(0 <= native['predictions'][0] <= 12)


class StreamlitTests(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        self.AppTest = AppTest
        self.environment = patch.dict(os.environ, {'API_BASE_URL': 'http://127.0.0.1:1',
            'PREDICTION_ADAPTER': 'subprocess', 'ML_PYTHON': os.environ.get('PHASE5_TEST_ML_PYTHON', '')})
        self.environment.start(); self.addCleanup(self.environment.stop)

    @staticmethod
    def mock_get(_client, path, **kwargs):
        if path == '/predictions/persistence-live':
            from backend.persistence_live import persistence_live
            return persistence_live(slots(datetime.now(timezone.utc))).model_dump(mode='json')
        if path == '/slots': return slots(datetime.now(timezone.utc))
        if path == '/stats': return {'total_slots': 12, 'occupied': 3, 'vacant': 9, 'unknown': 0}
        if path == '/health': return {'status': 'ok', 'database_ok': True, 'mqtt': {'connected': True, 'received': 0}}
        raise AssertionError(path)

    def app(self):
        return self.AppTest.from_file(str(ROOT/'dashboard/app.py'), default_timeout=25)

    def test_fresh_grid_counts_metrics_and_manual_refresh(self):
        with patch.object(ApiClient, 'get', self.mock_get):
            app = self.app().run()
            self.assertFalse(app.exception)
            self.assertEqual([m.value for m in app.metric], ['12', '3', '9', '0'])
            self.assertEqual(sum(m.value.startswith('**P') for m in app.markdown), 12)
            self.assertTrue(any('Random Forest' in m.value and '0.307714' in m.value for m in app.markdown))
            app.button(key='refresh_live').click().run()
            self.assertFalse(app.exception)

    def test_api_error_never_shows_fresh_counts(self):
        with patch.object(ApiClient, 'get', side_effect=ApiError('test outage')):
            app = self.app().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(app.error)
        self.assertEqual(sum(m.value.startswith('**P') for m in app.markdown), 12)
        self.assertTrue(any('Live prediction unavailable' in w.value for w in app.warning))

    def test_automatic_refresh_can_be_disabled_without_busy_loop(self):
        import streamlit
        with patch.object(ApiClient, 'get', self.mock_get), patch('streamlit.fragment', wraps=streamlit.fragment) as fragment:
            app = self.app().run()
            self.assertEqual(fragment.call_args.kwargs['run_every'], 10)
            app.toggle[0].set_value(False).run()
            self.assertIsNone(fragment.call_args.kwargs['run_every'])
            self.assertFalse(app.exception)

    def test_stale_snapshot_has_twelve_unknown_and_no_live_prediction(self):
        method = self.mock_get
        def getting(client, path, **kwargs):
            if path == '/slots': return slots(datetime.now(timezone.utc)-timedelta(minutes=1))
            return method(client, path, **kwargs)
        with patch.object(ApiClient, 'get', getting): app = self.app().run()
        self.assertFalse(app.exception)
        self.assertEqual([m.value for m in app.metric], ['12', '0', '0', '12'])
        self.assertFalse(any(b.key=='compute_live' for b in app.button))

    def test_history_chart_and_filter_invalidation(self):
        items = observations(datetime.now(timezone.utc).replace(second=0, microsecond=0))
        with patch.object(ApiClient, 'get', self.mock_get), patch.object(ApiClient, 'history', return_value=HistoryResult(items, 12, False)):
            app = self.app().run()
            next(b for b in app.button if b.label=='Load telemetry history').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.get('plotly_chart')), 1)
            app.selectbox[1].select('P1').run()
            self.assertEqual(len(app.get('plotly_chart')), 0)

    def test_history_truncation_and_failed_refresh_are_explicit(self):
        with patch.object(ApiClient, 'get', self.mock_get), patch.object(ApiClient, 'history', return_value=HistoryResult([], 100, True)):
            app = self.app().run()
            next(b for b in app.button if b.label=='Load telemetry history').click().run()
            self.assertTrue(any('Partial history' in w.value for w in app.warning))
        with patch.object(ApiClient, 'get', self.mock_get), patch.object(ApiClient, 'history', side_effect=ApiError('outage')):
            next(b for b in app.button if b.label=='Load telemetry history').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.get('plotly_chart')), 0)
            self.assertTrue(any('History unavailable' in e.value for e in app.error))

    def test_complete_fixture_history_calls_actual_saved_model(self):
        if not os.environ.get('PHASE5_TEST_ML_PYTHON'): self.skipTest('Approved ML interpreter required')
        origin = pd.Timestamp.now(tz='UTC').floor('min')
        frame = pd.DataFrame({'timestamp': pd.date_range(end=origin, periods=10081, freq='min').tz_convert(TIMEZONE), 'data_source': 'api_telemetry'})
        for index, slot in enumerate(SLOTS): frame[slot] = 1.0 if index < 3 else 0.0
        frame['total_occupied'] = 3.0
        with patch.object(ApiClient, 'get', self.mock_get), patch.object(ApiClient, 'history', return_value=HistoryResult([], 0, False)), patch('dashboard.app.minute_history', return_value=frame):
            # AppTest executes the entry point as __main__; patch the imported function at its source.
            with patch('dashboard.data_views.minute_history', return_value=frame):
                app = self.app().run()
                app.button(key='compute_live').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any(m.label=='Predicted occupied slots / 12' and m.value=='3.00' for m in app.metric))

    def test_incomplete_history_cannot_produce_live_forecast(self):
        with patch.object(ApiClient, 'get', self.mock_get), patch.object(ApiClient, 'history', return_value=HistoryResult([], 0, False)):
            app = self.app().run()
            app.button(key='compute_live').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Live prediction unavailable' in w.value for w in app.warning))
        self.assertFalse(any(m.label=='Predicted occupied slots / 12' for m in app.metric))

    def test_synthetic_example_genuine_worker_outputs_are_separate(self):
        if not os.environ.get('PHASE5_TEST_ML_PYTHON'): self.skipTest('Approved ML interpreter required')
        with patch.object(ApiClient, 'get', self.mock_get):
            app = self.app().run()
            next(b for b in app.button if b.label=='Run synthetic retrospective example').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any(s.value=='Synthetic retrospective prediction completed.' for s in app.success))
        self.assertTrue(any(m.label=='Synthetic predicted occupied / 12' for m in app.metric))
        self.assertEqual([m.value for m in app.metric][:4], ['12', '3', '9', '0'])


if __name__ == '__main__': unittest.main(verbosity=2)
