"""Record actual local tests and GET-only observations; never deploy or inject data."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import urlopen

from dashboard.api_client import ApiClient
from dashboard.config import ROOT, Settings
from dashboard.data_views import slot_snapshot


def run_suite(interpreter, directory):
    command = [str(interpreter), '-B', '-m', 'unittest', 'discover', '-s', directory, '-v']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=240)
    output = result.stdout + result.stderr
    count = re.search(r'Ran (\d+) tests', output)
    passed = result.returncode == 0 and count is not None and re.search(r'\nOK\s*$', output) is not None
    return {'command': command, 'exit_code': result.returncode, 'tests_run': int(count[1]) if count else 0,
            'passed': passed, 'skipped': 0 if passed else None, 'output': output}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ml-python', required=True, help='Approved compatible local ML interpreter')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preservation-snapshot', type=Path)
    parser.add_argument('--dashboard-url', default='http://127.0.0.1:8501')
    arguments = parser.parse_args()
    if arguments.output.exists(): parser.error('Choose a new evidence filename; existing results are preserved')
    os.environ['PHASE5_TEST_ML_PYTHON'] = arguments.ml_python
    report = {'source': 'actual_phase5_local_verification',
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'baseline_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    report['suites'] = {name: run_suite(interpreter, directory) for name, interpreter, directory in (
        ('dashboard', sys.executable, 'dashboard/tests'), ('backend', sys.executable, 'backend/tests'),
        ('ml', arguments.ml_python, 'ml/tests'))}
    report['test_total'] = sum(v['tests_run'] for v in report['suites'].values())
    report['all_tests_passed'] = all(v['passed'] for v in report['suites'].values())
    settings = Settings.from_env()
    client = ApiClient(settings)
    report['api_base_url'] = settings.api_base_url
    report['production_observation'] = {}
    for path in ('/slots', '/stats', '/health', '/history'):
        try:
            report['production_observation'][path] = client.get(path,
                params={'limit': 1} if path == '/history' else None, degraded_health=path == '/health')
        except Exception as error:
            report['production_observation'][path] = {'observation_error': str(error)}
    try:
        _, counts = slot_snapshot(report['production_observation']['/slots'], settings.stale_seconds)
        report['effective_live_counts'] = counts
    except (ValueError, TypeError):
        report['effective_live_counts'] = None
    report['http_service'] = {}
    for path in ('/', '/_stcore/health'):
        try:
            with urlopen(arguments.dashboard_url.rstrip('/') + path, timeout=5) as response:
                report['http_service'][path] = {'status': response.status,
                    'content_type': response.headers.get('Content-Type')}
        except OSError as error:
            report['http_service'][path] = {'error': str(error)}
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(ROOT/'dashboard/app.py'), default_timeout=30).run()
    ui = {'method': 'Streamlit AppTest against the existing local API; no browser control',
          'initial_exceptions': [e.message for e in app.exception],
          'live_metrics': [{'label': m.label, 'value': m.value} for m in app.metric],
          'warnings': [w.value for w in app.warning],
          'slot_cards': sum(m.value.startswith('**P') for m in app.markdown)}
    next(b for b in app.button if b.label == 'Load telemetry history').click().run()
    ui['history_exceptions'] = [e.message for e in app.exception]
    ui['history_plotly_charts'] = len(app.get('plotly_chart'))
    ui['history_messages'] = [i.value for i in app.info]
    next(b for b in app.button if b.label == 'Run synthetic retrospective example').click().run()
    ui['synthetic_exceptions'] = [e.message for e in app.exception]
    ui['synthetic_success'] = any(s.value == 'Synthetic retrospective prediction completed.' for s in app.success)
    ui['synthetic_metrics'] = [{'label': m.label, 'value': m.value} for m in app.metric if m.label.startswith('Synthetic')]
    report['actual_ui'] = ui
    report['runtime'] = {'frontend_python': sys.executable, 'ml_python': arguments.ml_python,
                         'prediction_adapter': settings.prediction_adapter,
                         'packages_installed_during_phase5': False, 'security_settings_changed': False}
    report['dependencies'] = {}
    for key, interpreter in (('frontend', sys.executable), ('ml', arguments.ml_python)):
        result = subprocess.run([str(interpreter), '-B', '-m', 'pip', 'freeze'], capture_output=True, text=True, timeout=30)
        if result.returncode: raise RuntimeError('Dependency inventory failed')
        report['dependencies'][key] = result.stdout.splitlines()
    expected_frontend = (ROOT/'requirements.txt').read_text(encoding='utf-8').splitlines()
    report['frontend_freeze_matches_frozen_requirements'] = sorted(report['dependencies']['frontend']) == sorted(expected_frontend)
    report['frozen_frontend_pins_preserved'] = set(expected_frontend).issubset(report['dependencies']['frontend'])
    report['frontend_extra_packages_beyond_frozen_snapshot'] = sorted(set(report['dependencies']['frontend']) - set(expected_frontend))
    report['environment_note'] = 'The project environment contains additional Jupyter packages beyond the historical requirements snapshot. No packages were installed, removed or upgraded by Phase 5.'
    notebook_evidence = json.loads((ROOT/'reports/evidence/notebook_execution_verification.json').read_text(encoding='utf-8'))
    report['ml_freeze_matches_pre_phase5_environment'] = sorted(report['dependencies']['ml']) == sorted(notebook_evidence['runtime']['packages_after_install'])
    report['protected_files'] = {}
    if arguments.preservation_snapshot:
        snapshot = json.loads(arguments.preservation_snapshot.read_text(encoding='utf-8'))
        baseline_time = arguments.preservation_snapshot.stat().st_mtime
        extras = {}
        for pin in report['frontend_extra_packages_beyond_frozen_snapshot']:
            metadata = Path(importlib.metadata.distribution(pin.split('==')[0])._path)
            extras[pin] = {'metadata_created_utc': datetime.fromtimestamp(metadata.stat().st_ctime, timezone.utc).isoformat(),
                           'predates_phase5_snapshot': metadata.stat().st_ctime < baseline_time}
        report['preexisting_extra_package_metadata'] = extras
        report['protected_files'] = snapshot['sha256']
        report['protected_hashes_preserved'] = all(Path(p).is_file() and
            hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in snapshot['sha256'].items())
    else:
        report['protected_hashes_preserved'] = None
    report['local_functional_passed'] = bool(report['all_tests_passed'] and not ui['initial_exceptions']
        and not ui['history_exceptions'] and not ui['synthetic_exceptions'] and ui['synthetic_success']
        and ui['slot_cards'] == 12 and all(v.get('status') == 200 for v in report['http_service'].values())
        and report['frozen_frontend_pins_preserved'] and report['ml_freeze_matches_pre_phase5_environment']
        and report['protected_hashes_preserved'] is not False)
    report['limitations'] = [
        'AppTest and local HTTP verified; browser visual interaction and wall-clock auto-refresh scheduling were not independently observed.',
        'Refresh interval registration, disabling and manual reruns were tested through AppTest.',
        'Complete-history live forecast path used explicit test fixtures with the actual saved model; no production forecast success is claimed.',
        'Synthetic retrospective predictions and holdout scores are not real-world accuracy evidence.',
        'Cloud deployment, Linux wheel compatibility, public API security and persistent hosted infrastructure remain unverified Phase 6 work.']
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: report[k] for k in ('test_total', 'all_tests_passed', 'effective_live_counts', 'local_functional_passed')}, indent=2))
    if not report['local_functional_passed']: raise SystemExit(1)


if __name__ == '__main__': main()
