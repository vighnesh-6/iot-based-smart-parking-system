"""Separate Persistence UI tests; all success observations are isolated fixtures."""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from backend.persistence_live import persistence_live
from dashboard.api_client import ApiClient, ApiError
import test_dashboard as existing
from test_dashboard import slots


class PersistencePanelTests(unittest.TestCase):
    setUp = existing.StreamlitTests.setUp
    app = existing.StreamlitTests.app
    def fixture_get(self, available=True, unavailable_reason=None):
        def getting(client, path, **kwargs):
            if path == '/predictions/persistence-live':
                if unavailable_reason: raise ApiError(unavailable_reason)
                now = datetime.now(timezone.utc)
                rows = slots(now)
                for row in rows: row['measured_at'] = now.isoformat()
                if not available: rows[0]['stale'] = True
                return persistence_live(rows).model_dump(mode='json')
            return existing.StreamlitTests.mock_get(client, path, **kwargs)
        return getting

    def test_available_fixture_displays_equal_counts_and_separate_label(self):
        with patch.object(ApiClient, 'get', self.fixture_get()), patch('dashboard.prediction.predict') as full_model:
            app = self.app().run()
            self.assertFalse(app.exception)
            values = {m.label: m.value for m in app.metric}
            self.assertEqual(values['Current complete occupancy / 12'], '3')
            self.assertEqual(values['Persistence-only forecast at +15 minutes / 12'], '3')
            self.assertTrue(any('not the 37-feature' in c.value for c in app.caption))
            self.assertTrue(any('Last successful Persistence-only prediction:' in c.value for c in app.caption))
            self.assertEqual(full_model.call_count, 0)
            app.button(key='refresh_live').click().run()
            self.assertFalse(app.exception)

    def test_stale_response_hides_forecast_and_explains_blocked_slot(self):
        with patch.object(ApiClient, 'get', self.fixture_get(False)):
            app = self.app().run()
        self.assertFalse(app.exception)
        self.assertFalse(any(m.label.startswith('Persistence-only forecast') for m in app.metric))
        self.assertTrue(any('Persistence-only live prediction unavailable' in w.value for w in app.warning))
        self.assertTrue(any('Backend marks observation stale' in str(frame.value) for frame in app.dataframe))

    def test_prediction_api_error_does_not_break_existing_pages(self):
        with patch.object(ApiClient, 'get', self.fixture_get(unavailable_reason='HTTP 503')):
            app = self.app().run()
        self.assertFalse(app.exception)
        self.assertEqual(sum(m.value.startswith('**P') for m in app.markdown), 12)
        self.assertTrue(any('HTTP 503' in w.value for w in app.warning))

    def test_cached_success_expires_and_does_not_keep_showing_old_forecast(self):
        getter = self.fixture_get()
        response = getter(None, '/predictions/persistence-live')
        old = datetime.now(timezone.utc)-timedelta(seconds=31)
        for row in response['snapshot']: row.update(received_at=old.isoformat(), measured_at=old.isoformat())
        def getting(client, path, **kwargs):
            return response if path == '/predictions/persistence-live' else existing.StreamlitTests.mock_get(client, path, **kwargs)
        with patch.object(ApiClient, 'get', getting): app = self.app().run()
        self.assertFalse(app.exception)
        self.assertFalse(any(m.label.startswith('Persistence-only forecast') for m in app.metric))
