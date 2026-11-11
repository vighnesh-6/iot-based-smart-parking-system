# Phase 3 dataset acceptance checklist

All listed data checks are critical. Synthetic data does not establish real-world performance.

| Requirement | Result | Evidence |
| --- | --- | --- |
| eight_weeks_one_minute | PASS | phase3_dataset_validation.json: checks.eight_weeks_one_minute |
| all_twelve_slots | PASS | phase3_dataset_validation.json: checks.all_twelve_slots |
| synthetic_provenance | PASS | phase3_dataset_validation.json: checks.synthetic_provenance |
| missing_values_and_numeric_ranges | PASS | phase3_dataset_validation.json: checks.missing_values_and_numeric_ranges |
| total_equals_slot_sum | PASS | phase3_dataset_validation.json: checks.total_equals_slot_sum |
| slot_arrivals_departures_and_dwell | PASS | phase3_dataset_validation.json: checks.slot_arrivals_departures_and_dwell |
| synthetic_daily_weekly_patterns | PASS | phase3_dataset_validation.json: checks.synthetic_daily_weekly_patterns |
| exact_fifteen_minute_target | PASS | phase3_dataset_validation.json: checks.exact_fifteen_minute_target |
| current_features_match_observation | PASS | phase3_dataset_validation.json: checks.current_features_match_observation |
| all_lags_are_past_only | PASS | phase3_dataset_validation.json: checks.all_lags_are_past_only |
| all_rolling_windows_exclude_future | PASS | phase3_dataset_validation.json: checks.all_rolling_windows_exclude_future |
| calendar_and_change_features | PASS | phase3_dataset_validation.json: checks.calendar_and_change_features |
| future_intervention_and_prefix_invariance | PASS | phase3_dataset_validation.json: checks.future_intervention_and_prefix_invariance |
| chronological_70_15_15_purged_boundaries | PASS | phase3_dataset_validation.json: checks.chronological_70_15_15_purged_boundaries |
| schema_predictor_allowlist | PASS | phase3_dataset_validation.json: checks.schema_predictor_allowlist |
| fixed_seed_full_reproducibility | PASS | phase3_dataset_validation.json: checks.fixed_seed_full_reproducibility |
| artifact_checksums | PASS | phase3_dataset_validation.json: checks.artifact_checksums |
| storage_below_50_MB | PASS | phase3_dataset_validation.json: checks.storage_below_50_MB |

Dataset acceptance: PASS.

Software tests, scope preservation and final PDF visual verification are recorded separately in phase3_final_checks.json.

## Final delivery acceptance

| Requirement | Result | Evidence |
| --- | --- | --- |
| All critical full-dataset validations | PASS | phase3_dataset_validation.json: 18/18 |
| Relevant software tests | PASS | phase3_tests.json: 21 passed; zero skips/errors/failures |
| Frozen Phase 1/2 implementation and artifacts | PASS | phase3_final_checks.json: protected paths unchanged |
| Wokwi observations and live database separation | PASS | No MQTT/SQLite input or writes in the data pipeline; scope verification |
| Existing notebooks and training placeholder preserved | PASS | Protected-path verification; no notebook generator or model training |
| Reproducible dataset bytes across Git checkouts | PASS | .gitattributes disables EOL conversion for released data; file hashes verified |
| Lightweight storage and no duplicate split files | PASS | 7,327,764 bytes in data/model directories; one raw and one processed table |
| Usable compressed processed format | PASS | CSV.gz round-trip and byte reproducibility verified; Parquet DLL blocked and unverified |
| Complete report and visual inspection | PASS | phase3_final_checks.json: ten rendered pages inspected |

Phase 3 acceptance: **PASS**. This certifies synthetic dataset preparation only,
not real-world model accuracy or Wokwi runtime performance. Version-control
delivery is verified after the final single push.
