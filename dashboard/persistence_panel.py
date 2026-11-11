"""Display the separate backend Persistence forecast without replacing full ML."""
from datetime import datetime, timezone

import streamlit as st

from backend.persistence_live import PersistenceLiveResult, persistence_live
from dashboard.api_client import ApiError


def show_persistence_live(client, settings):
    st.subheader('Persistence-only live inference')
    st.caption('Separate inference path: occupied(t + 15 minutes) = occupied(t). '
               'Uses a fresh complete twelve-slot snapshot; not the 37-feature ML pipeline.')
    try:
        result = PersistenceLiveResult.model_validate(client.get('/predictions/persistence-live'))
        # Recheck server snapshot at display time, including client freshness ceiling.
        # This prevents a delayed/cached successful response becoming a stale forecast.
        checked = persistence_live(result.snapshot, min(settings.stale_seconds, result.freshness_limit_seconds))
        if result.available and not checked.available:
            result = checked
        elif result.available and result.current_occupied != checked.current_occupied:
            raise ValueError('API count does not match its complete snapshot')
        st.caption(f'Freshness checked: {result.evaluated_at.isoformat()} · '
                   f'limit {result.freshness_limit_seconds}s for receipt and measurement.')
        if result.available:
            st.session_state['persistence_last_prediction'] = result.prediction_timestamp.isoformat()
            left, right = st.columns(2)
            left.metric('Current complete occupancy / 12', result.current_occupied)
            right.metric('Persistence-only forecast at +15 minutes / 12', result.predicted_occupied)
            st.caption(f'Prediction origin: {result.prediction_timestamp.isoformat()} · '
                       f'target: {result.target_timestamp.isoformat()} · source: genuine API/SQLite observations.')
        else:
            st.warning('Persistence-only live prediction unavailable: every slot must have fresh, known, timestamped observations.')
            st.dataframe(result.blockers, hide_index=True, width='stretch')
        st.caption('Last successful Persistence-only prediction: ' +
                   st.session_state.get('persistence_last_prediction', 'none in this dashboard session'))
        st.caption('Refreshes with the live panel when automatic refresh is enabled; Refresh now also checks new telemetry. '
                   'No synthetic fallback and no stale forecast value is displayed.')
    except (ApiError, ValueError, TypeError, KeyError) as error:
        st.warning(f'Persistence-only live prediction unavailable: {error}')
