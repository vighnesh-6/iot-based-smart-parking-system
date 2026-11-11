"""Local-first Streamlit UI. Launch: python -m streamlit run dashboard/app.py."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import plotly.graph_objects as go
import streamlit as st

from dashboard.api_client import ApiClient, ApiError
from dashboard.config import Settings
from dashboard import data_views as _views

# A running Streamlit process can retain the pre-Phase-6 module across reruns.
if not all(callable(getattr(_views, name, None)) for name in
           ('live_feature_record', 'minute_history', 'slot_snapshot', 'slot_history')):
    from importlib import reload
    reload(_views)

from dashboard.data_views import live_feature_record, minute_history, slot_snapshot, slot_history
from dashboard.prediction import PredictionError, predict, read_results, synthetic_example


def show_slots(slots=None):
    indexed = {s['slot_id']: s for s in slots or []}
    for board, column in enumerate(st.columns(3), start=1):
        with column:
            st.markdown(f'### ESP32-{board:02d}')
            for number in range(4 * board - 3, 4 * board + 1):
                slot_id = f'P{number}'
                item = indexed.get(slot_id)
                status = item['display_status'] if item else 'UNKNOWN'
                color = {'VACANT': 'green', 'OCCUPIED': 'red', 'UNKNOWN': 'gray'}[status]
                with st.container(border=True):
                    st.markdown(f'**{slot_id}** · :{color}[{status.title()}]')
                    st.caption(item['reason'] if item else 'API unavailable')
                    if item and item['observed']:
                        age = max(0, int(item['age_seconds'])) if item['age_seconds'] is not None else None
                        st.caption(f"Last receipt: {item['received_at']} · age {age}s")
                        st.caption(f"Measurement time: {item['measured_at'] or 'unavailable (unsynchronized device clock)'}")
                        distance = item['distance_cm']
                        st.caption(f"Last reported: {item['occupancy_status']} · distance {distance if distance is not None else 'unavailable'} cm")


def draw_history(frame, slot_id=None):
    figure = go.Figure()
    if slot_id:
        values = [None if value != value else float(value) for value in frame[slot_id]]
        figure.add_trace(go.Scatter(x=frame.timestamp.tolist(), y=values, mode='lines+markers',
            name=slot_id, connectgaps=False, line={'color': '#007f86', 'shape': 'hv'}))
        figure.update_yaxes(title='0 Vacant / 1 Occupied', range=[-0.1, 1.1], dtick=1)
    else:
        values = [None if value != value else float(value) for value in frame.total_occupied]
        figure.add_trace(go.Scatter(x=frame.timestamp.tolist(), y=values, mode='lines',
            name='Occupied (complete snapshots)', connectgaps=False, line={'color': '#007f86'}))
        figure.add_trace(go.Scatter(x=frame.timestamp.tolist(), y=frame.known_slots.tolist(),
            mode='lines', name='Known slot coverage', line={'color': '#b98132', 'dash': 'dot'}))
        figure.update_yaxes(title='Slots', range=[-0.2, 12.5], dtick=2)
    figure.update_layout(height=350, margin={'l': 20, 'r': 20, 't': 20, 'b': 20},
        xaxis_title=('Observation receipt (Asia/Kolkata)' if slot_id else
                     'Minute origin (Asia/Kolkata; receipt-time reconstruction)'),
        legend={'orientation': 'h'}, template='plotly_white')
    st.plotly_chart(figure, width='stretch')


def main():
    st.set_page_config(page_title='Smart Parking | 12-slot operations', page_icon='🅿️', layout='wide')
    try:
        settings = Settings.from_env()
    except (ValueError, OSError) as error:
        st.error(f'Dashboard configuration is invalid: {error}')
        st.stop()
    client = ApiClient(settings)
    st.title('Smart Parking')
    st.caption('12 SLOTS  /  3 ESP32 BOARDS  /  LIVE API + SYNTHETIC MODEL REVIEW')
    with st.sidebar:
        st.header('Connection & refresh')
        st.caption(f'FastAPI: {settings.api_base_url}')
        automatic = st.toggle('Automatic refresh', value=True)
        interval = st.select_slider('Refresh interval (seconds)', options=[5, 10, 15, 30, 60], value=settings.refresh_seconds)
        st.caption(f'Prediction adapter: {settings.prediction_adapter}')
        st.caption(f'Client freshness ceiling: {settings.stale_seconds}s. Backend stale flags also apply.')
        st.info('Unknown and stale readings are never counted as available spaces.')
        st.caption('Local verification only. Cloud deployment is not complete.')

    live_tab, history_tab, model_tab = st.tabs(['Live operations', 'Telemetry history', 'Models & synthetic review'])

    @st.fragment(run_every=interval if automatic else None)
    def live_panel():
        st.subheader('Current parking availability')
        st.button('Refresh now', key='refresh_live')
        try:
            with st.spinner('Reading the parking API…'):
                slots, counts = slot_snapshot(client.get('/slots'), settings.stale_seconds)
            st.caption(f"Snapshot retrieved: {datetime.now(timezone.utc).isoformat(timespec='seconds')} · receipt-based freshness")
            for column, label, value in zip(st.columns(4), ['Capacity', 'Occupied', 'Vacant', 'Unknown'],
                                          [12, counts['occupied'], counts['vacant'], counts['unknown']]):
                column.metric(label, value)
            if counts['unknown']:
                st.warning(f"{counts['unknown']} slots are unknown; {counts['stale']} stale and {counts['unseen']} never observed. Diagnostic counts can overlap.")
            show_slots(slots)
        except (ApiError, ValueError, TypeError) as error:
            st.error(f'Live readings unavailable. {error}')
            st.info('No fresh counts or live forecast can be established. Check the API connection.')
            show_slots()
            slots, counts = None, None

        st.subheader('15-minute occupancy forecast')
        st.caption('Selected model: Persistence. Trained/evaluated on synthetic history; no real-world accuracy claim.')
        if not counts or counts['unknown']:
            st.warning('Live prediction unavailable — all 12 slots must have fresh, known observations.')
        else:
            st.caption('A complete seven-day causal minute history is also required by the frozen 37-feature interface.')
            if st.button('Compute live forecast', key='compute_live'):
                try:
                    with st.spinner('Checking history and calculating the forecast…'):
                        origin = datetime.now(timezone.utc).replace(second=0, microsecond=0)
                        start = origin - timedelta(days=7)
                        history = client.history(since=(start - timedelta(seconds=settings.stale_seconds)).isoformat(), until=origin.isoformat())
                        if history.truncated:
                            raise ValueError('History fetch was capped; completeness cannot be established. No forecast produced.')
                        minutes = minute_history(history.items, start, origin, settings.stale_seconds)
                        features = live_feature_record(minutes)
                        forecast = predict(features, settings)
                    st.metric('Predicted occupied slots / 12', f"{forecast['predictions'][0]:.2f}")
                    st.caption(f'Origin: {origin.isoformat()} · target: {(origin + timedelta(minutes=15)).isoformat()} · input: API telemetry')
                except (ApiError, ValueError, PredictionError, OSError) as error:
                    st.warning(f'Live prediction unavailable. {error}')
        with st.expander('Backend & MQTT diagnostics'):
            try:
                health = client.get('/health', degraded_health=True)
                if not isinstance(health, dict) or health.get('status') not in ('ok', 'degraded'):
                    raise ValueError('Invalid health response')
                if health['status'] != 'ok':
                    st.warning('Backend reports degraded health.')
                st.json(health)
                last_received = health.get('mqtt', {}).get('last_received_at')
                if last_received:
                    age = (datetime.now(timezone.utc) - datetime.fromisoformat(last_received.replace('Z', '+00:00'))).total_seconds()
                    if age < -2:
                        st.warning('Telemetry receipt clock is ahead; delivery freshness cannot be trusted.')
                    elif age > settings.stale_seconds:
                        st.warning(f'No recent MQTT delivery: last receipt {age:.0f}s ago.')
                    else:
                        st.caption(f'MQTT last receipt: {age:.0f}s ago. Check individual cards for board coverage.')
                else:
                    st.warning('This backend process has not received production telemetry yet.')
                st.caption('Connected/subscribed indicates transport readiness, not successful sensor delivery. Counters are per backend process.')
            except (ApiError, ValueError) as error:
                st.warning(f'Health unavailable. {error}')
            try:
                st.json({'backend_statistics': client.get('/stats')})
                st.caption('Separate API requests are not atomic. Headline counts use the same validated snapshot as the cards.')
            except ApiError as error:
                st.warning(f'Statistics unavailable. {error}')

    with live_tab:
        live_panel()
    with history_tab:
        st.subheader('Observed telemetry history')
        st.caption('Live API observations only. No synthetic records are inserted or mixed into this view.')
        hours = st.selectbox('History window', [1, 24, 168], index=1, format_func=lambda h: f'{h} hours')
        selected = st.selectbox('Slot filter', ['All slots', *[f'P{i}' for i in range(1, 13)]])
        signature = (hours, selected)
        if st.session_state.get('history_signature') != signature:
            st.session_state.pop('history_view', None)
        if st.button('Load telemetry history'):
            st.session_state.pop('history_view', None)
            try:
                end = datetime.now(timezone.utc)
                start = end - timedelta(hours=hours)
                with st.spinner('Fetching bounded history pages…'):
                    history = client.history(since=(start - timedelta(seconds=settings.stale_seconds)).isoformat(),
                        until=end.isoformat(), slot_id=None if selected == 'All slots' else selected)
                    minutes = (minute_history(history.items, start, end, settings.stale_seconds)
                        if selected == 'All slots' else
                        slot_history(history.items, selected, start, end, settings.stale_seconds))
                st.session_state['history_view'] = (minutes, history.total, len(history.items), history.truncated, end)
                st.session_state['history_signature'] = signature
            except (ApiError, ValueError, OSError) as error:
                st.error(f'History unavailable. {error}')
        if 'history_view' in st.session_state:
            minutes, total, loaded, truncated, end = st.session_state['history_view']
            st.caption(f'{loaded} of {total} observations loaded · upper receipt bound: {end.isoformat()}')
            if truncated:
                st.warning('Partial history: row/time cap reached. Gaps and coverage are shown; completeness is not established.')
            if not loaded:
                st.info('No observations in this window.')
            elif selected == 'All slots' and not minutes.total_occupied.notna().any():
                st.info('No complete fresh 12-slot minute snapshots exist in this window. A total occupancy trend cannot be established.')
            draw_history(minutes, None if selected == 'All slots' else selected)
            if selected != 'All slots':
                st.caption(f'{minutes[selected].notna().sum()} known-state observations plotted at actual receipt times. UNKNOWN readings and long gaps break the line. Closely spaced receipts may overlap; zoom to inspect.')
            st.caption('Only accepted-current observations contribute. UNKNOWN, missing or expired readings produce gaps. No backward fill or future observations are used.')
        else:
            st.info('Choose a window and load history. The result is a historical extraction, not an automatically refreshed live feed.')

    with model_tab:
        st.subheader('Frozen Phase 4 model comparison')
        st.info('SYNTHETIC EVALUATION — these scores do not establish real-world accuracy.')
        try:
            results = read_results(settings)
            lines = ['| Partition | Model | MAE | RMSE | R² |', '| --- | --- | ---: | ---: | ---: |']
            names = {'persistence': 'Persistence Baseline', 'linear_regression': 'Linear Regression', 'random_forest': 'Random Forest'}
            for split in ('validation', 'test'):
                for name in names:
                    score = results[split][name]['clipped']
                    lines.append(f"| {split.title()} | {names[name]} | {score['mae']:.6f} | {score['rmse']:.6f} | {score['r2']:.6f} |")
            st.markdown('\n'.join(lines))
            st.caption('MAE/RMSE are occupied-slot counts. Same held-out rows; predictions clipped to 0–12 without rounding. Persistence won validation MAE; test data did not select the model.')
            st.subheader('Synthetic retrospective forecast')
            st.caption('Explicitly separate from live telemetry: evaluate the saved model on an existing frozen validation feature row. No regeneration or retraining.')
            if st.button('Run synthetic retrospective example'):
                try:
                    with st.spinner('Loading the trusted model through the configured adapter…'):
                        example = synthetic_example(settings)
                    st.success('Synthetic retrospective prediction completed.')
                    left, right = st.columns(2)
                    left.metric('Synthetic predicted occupied / 12', f"{example['predictions'][0]:.2f}")
                    right.metric('Synthetic actual at t+15', f"{example['actual_future_occupied']:.0f}")
                    st.caption(f"Synthetic validation origin: {example['origin']} · horizon: 15 minutes · model: {example['selected_model']}")
                except (PredictionError, ValueError, OSError) as error:
                    st.error(f'Synthetic example unavailable. {error}')
        except (ValueError, KeyError, OSError) as error:
            st.error(f'Model evaluation artifacts unavailable. {error}')
    st.caption('Phase 5 · read-only dashboard · database and telemetry remain owned by the existing backend')


if __name__ == '__main__':
    main()
