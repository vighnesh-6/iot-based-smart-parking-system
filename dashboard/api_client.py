"""Bounded, GET-only FastAPI client. No SQLite/MQTT access or writes."""
from dataclasses import dataclass
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ApiError(RuntimeError):
    pass


@dataclass
class HistoryResult:
    items: list
    total: int
    truncated: bool


class ApiClient:
    def __init__(self, settings):
        self.settings = settings

    def get(self, path, *, params=None, degraded_health=False):
        if path not in ('/slots', '/stats', '/health', '/history', '/predictions/persistence-live'):
            raise ValueError('Unsupported read-only endpoint')
        url = self.settings.api_base_url.rstrip('/') + path
        if params:
            url += '?' + urlencode({k: v for k, v in params.items() if v is not None})
        headers = {'Accept': 'application/json'}
        if self.settings.api_bearer_token:
            headers['Authorization'] = 'Bearer ' + self.settings.api_bearer_token
        request = Request(url, headers=headers, method='GET')
        try:
            try:
                response = urlopen(request, timeout=self.settings.timeout_seconds)
            except HTTPError as error:
                if degraded_health and path == '/health' and error.code == 503:
                    response = error
                else:
                    raise ApiError(f'{path}: API returned HTTP {error.code}') from error
            with response:
                content = response.read(4_000_001)
            if len(content) > 4_000_000:
                raise ApiError(f'{path}: response exceeded the size limit')
            return json.loads(content)
        except (URLError, TimeoutError, OSError) as error:
            raise ApiError(f'{path}: API unreachable or request timed out') from error
        except (ValueError, UnicodeError) as error:
            raise ApiError(f'{path}: invalid JSON response') from error

    def history(self, *, since, until, slot_id=None):
        items, total = [], None
        started = time.monotonic()
        # Freeze the upper receipt-time bound so new arrivals cannot shift pages.
        while len(items) < self.settings.history_max_rows:
            if time.monotonic() - started > 20:
                return HistoryResult(items, total or len(items), True)
            limit = min(1000, self.settings.history_max_rows - len(items))
            page = self.get('/history', params={'since': since, 'until': until,
                'slot_id': slot_id, 'limit': limit, 'offset': len(items)})
            if not isinstance(page, dict) or not isinstance(page.get('items'), list):
                raise ApiError('/history: malformed page')
            count = page.get('total')
            if type(count) is not int or count < 0 or page.get('offset') != len(items) or page.get('limit') != limit:
                raise ApiError('/history: invalid pagination metadata')
            if total is not None and count != total:
                raise ApiError('/history: history changed while paging; retry')
            total = count
            batch = page['items']
            if len(batch) > limit or len(items) + len(batch) > total:
                raise ApiError('/history: inconsistent page length')
            items.extend(batch)
            if len(items) >= total:
                return HistoryResult(items, total, False)
            if not batch:
                raise ApiError('/history: incomplete page before end of history')
        return HistoryResult(items, total or 0, True)
