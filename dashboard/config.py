"""Portable dashboard configuration. Importing this module performs no I/O."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import tomllib
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    api_base_url: str = 'http://127.0.0.1:8000'
    api_bearer_token: str = field(default='', repr=False)
    prediction_adapter: str = 'in_process'
    ml_python: str = ''
    timeout_seconds: float = 3
    refresh_seconds: int = 10
    stale_seconds: int = 30
    history_max_rows: int = 20000
    results_path: Path = ROOT / 'ml/artifacts/phase4/model_results.json'
    model_path: Path = ROOT / 'ml/artifacts/phase4/parking_models.joblib'
    manifest_path: Path = ROOT / 'ml/data/phase3_dataset_manifest.json'

    def __post_init__(self):
        url = urlsplit(self.api_base_url)
        if url.scheme not in ('http', 'https') or not url.netloc or url.username or url.password or url.query or url.fragment:
            raise ValueError('API_BASE_URL must be an HTTP(S) base URL without credentials, query or fragment')
        if self.prediction_adapter not in ('in_process', 'subprocess'):
            raise ValueError('PREDICTION_ADAPTER must be in_process or subprocess')
        if not 0 < self.timeout_seconds <= 30 or self.refresh_seconds not in (5, 10, 15, 30, 60):
            raise ValueError('Invalid API timeout or refresh interval')
        if not 1 <= self.stale_seconds <= 300 or not 12 <= self.history_max_rows <= 2_000_000:
            raise ValueError('Invalid freshness limit or history row cap')

    @classmethod
    def from_env(cls):
        config_file = os.environ.get('DASHBOARD_CONFIG')
        config = {}
        if config_file:
            path = Path(config_file).expanduser()
            if not path.is_absolute():
                path = ROOT / path
            with path.open('rb') as stream:
                config = tomllib.load(stream)
        values = {**config, **os.environ}
        def value(name, default):
            return values.get(name, default)
        def path(name, default):
            result = Path(value(name, default)).expanduser()
            return result if result.is_absolute() else ROOT / result
        return cls(api_base_url=str(value('API_BASE_URL', cls.api_base_url)).rstrip('/'),
                   api_bearer_token=str(value('API_BEARER_TOKEN', '')),
                   prediction_adapter=str(value('PREDICTION_ADAPTER', cls.prediction_adapter)),
                   ml_python=str(value('ML_PYTHON', '')),
                   timeout_seconds=float(value('API_TIMEOUT_SECONDS', cls.timeout_seconds)),
                   refresh_seconds=int(value('REFRESH_SECONDS', cls.refresh_seconds)),
                   stale_seconds=int(value('DASHBOARD_STALE_SECONDS', cls.stale_seconds)),
                   history_max_rows=int(value('HISTORY_MAX_ROWS', cls.history_max_rows)),
                   results_path=path('MODEL_RESULTS_PATH', cls.results_path),
                   model_path=path('MODEL_BUNDLE_PATH', cls.model_path),
                   manifest_path=path('DATASET_MANIFEST_PATH', cls.manifest_path))
