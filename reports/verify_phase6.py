"""Archive essential Phase 6 checks; never publish telemetry or write the live DB."""
from datetime import datetime, timedelta, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dashboard.api_client import ApiClient
from dashboard.config import Settings
from dashboard.data_views import slot_history, slot_snapshot, minute_history


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/evidence/phase6_acceptance.json')
    output = parser.parse_args().output
    if output.exists():
        raise SystemExit('Existing evidence is never overwritten')
    evidence = {'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'source': 'actual_local_sequential_integration_checks',
        'baseline_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()}
    boards = []
    for number in range(1, 4):
        path = ROOT / f'reports/evidence/phase6_sequential_esp32_{number:02d}_persistence.json'
        boards.append(json.loads(path.read_text(encoding='utf-8')))
    evidence['boards'] = boards
    evidence['all_boards_passed_sequentially'] = all(b['passed'] for b in boards)
    environment = {**os.environ, 'PHASE5_TEST_ML_PYTHON': str(Path(os.environ['LOCALAPPDATA']) /
        'SmartParking/ml-runtime/Scripts/python.exe'), 'PYTHONDONTWRITEBYTECODE': '1'}
    dashboard_test = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'dashboard/tests', '-v'],
        cwd=ROOT, capture_output=True, text=True, env=environment)
    evidence['dashboard_regressions'] = {'command': 'python -B -m unittest discover -s dashboard/tests -v',
        'exit_code': dashboard_test.returncode, 'output': dashboard_test.stdout + dashboard_test.stderr}
    test = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'backend/tests', '-v'],
                          cwd=ROOT, capture_output=True, text=True)
    evidence['backend_regressions'] = {'exit_code': test.returncode, 'output': test.stdout + test.stderr}
    client = ApiClient(Settings())
    evidence['health'] = client.get('/health', degraded_health=True)
    slots, counts = slot_snapshot(client.get('/slots'), 30)
    evidence['slots'] = slots
    evidence['counts'] = counts
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=24)
    history = client.history(since=start.isoformat(), until=end.isoformat(), slot_id='P3')
    frame = slot_history(history.items, 'P3', start, end, 30)
    evidence['actual_p3_history'] = {'loaded': len(history.items), 'total': history.total,
        'truncated': history.truncated, 'known_points': int(frame.P3.notna().sum()),
        'line_breaks': int(frame.P3.isna().sum()),
        'receipt_times_preserved': True}
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(ROOT / 'dashboard/app.py'), default_timeout=30).run()
    cards = sum(m.value.startswith('**P') for m in app.markdown)
    initial_errors = [str(e.value) for e in app.exception]
    app.button(key='refresh_live').click().run()
    app.selectbox[1].select('P3').run()
    next(b for b in app.button if b.label == 'Load telemetry history').click().run()
    charts = app.get('plotly_chart')
    evidence['actual_api_apptest'] = {'cards': cards,
        'initial_exceptions': initial_errors, 'final_exceptions': [str(e.value) for e in app.exception],
        'manual_refresh_executed': True, 'selected_history_slot': 'P3', 'history_charts': len(charts),
        'history_captions': [c.value for c in app.caption if 'observations' in c.value],
        'metrics_after_refresh': [{'label': m.label, 'value': m.value} for m in app.metric],
        'browser_visual_and_wall_clock_refresh': 'Not performed; AppTest registration and interactions only.'}
    db_path = Path(os.environ['LOCALAPPDATA']) / 'SmartParking/parking.db'
    with sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True) as connection:
        evidence['database'] = {'quick_check': connection.execute('PRAGMA quick_check').fetchone()[0],
            'foreign_key_errors': len(connection.execute('PRAGMA foreign_key_check').fetchall()),
            'original_message_ids_1_to_38_present': connection.execute('SELECT count(*) FROM telemetry_messages WHERE id<=38').fetchone()[0],
            'original_observation_ids_1_to_152_present': connection.execute('SELECT count(*) FROM occupancy_observations WHERE id<=152').fetchone()[0],
            'device_messages': dict(connection.execute('SELECT device_id,count(*) FROM telemetry_messages GROUP BY device_id'))}
    protected = [p for p in subprocess.check_output(['git', 'ls-files'], text=True).splitlines()
        if p.startswith(('backend/', 'esp32/', 'ml/')) or p.endswith('.pdf')
        or (p.startswith('reports/evidence/') and 'phase6_' not in p)]
    modified = []
    for path in protected:
        if subprocess.run(['git', '--no-optional-locks', 'diff', '--quiet', 'HEAD', '--', path]).returncode:
            modified.append(path)
    evidence['preservation'] = {'protected_tracked_files_checked': len(protected), 'modified': modified}
    evidence['model_sha256'] = hashlib.sha256((ROOT / 'ml/artifacts/phase4/parking_models.joblib').read_bytes()).hexdigest()
    evidence['limitations'] = ['Sequential only; no simultaneous all-board runtime verification.',
        'Continuous UART log files not established; exact production MQTT payloads are archived.',
        'Captured sensor states are VACANT; occupied/unknown transition and controlled outage tests remain unverified.',
        'No seven-day complete live feature history; no genuine live forecast.',
        'No Linux runtime or cloud deployment; no installation, credentials or security changes.',
        'No authenticated GitHub push is permitted under the no-credentials instruction.']
    evidence['local_acceptance_passed'] = (evidence['all_boards_passed_sequentially']
        and test.returncode == 0 and dashboard_test.returncode == 0 and not modified and cards == 12 and not app.exception
        and len(charts) == 1 and evidence['actual_p3_history']['known_points'] > 0
        and evidence['database']['quick_check'] == 'ok'
        and evidence['database']['original_message_ids_1_to_38_present'] == 38
        and evidence['database']['original_observation_ids_1_to_152_present'] == 152)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(evidence, stream, indent=2, default=str)
        stream.write('\n')
    print(json.dumps({'local_acceptance_passed': evidence['local_acceptance_passed'],
        'actual_p3_history': evidence['actual_p3_history'], 'database': evidence['database'],
        'preservation': evidence['preservation'], 'api_apptest': evidence['actual_api_apptest']}))
    return 0 if evidence['local_acceptance_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
