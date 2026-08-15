from __future__ import annotations

from tests.test_bpm_prediction_compatibility import should_run_bpm_prediction_compatibility
from tests.test_end_to_end import should_run_real_cdlg_integration


def test_given_global_integration_flag_when_checked_then_real_cdlg_smoke_stays_disabled():
    assert not should_run_real_cdlg_integration({"CDLGW_RUN_INTEGRATION": "1"})


def test_given_specific_real_cdlg_flag_when_checked_then_real_cdlg_smoke_is_enabled():
    assert should_run_real_cdlg_integration({"CDLGW_RUN_REAL_CDLG": "1"})


def test_given_global_integration_flag_when_checked_then_bpm_prediction_smoke_stays_disabled():
    assert not should_run_bpm_prediction_compatibility({"CDLGW_RUN_INTEGRATION": "1"})


def test_given_specific_bpm_prediction_flag_when_checked_then_bpm_prediction_smoke_is_enabled():
    assert should_run_bpm_prediction_compatibility({"CDLGW_RUN_BPM_COMPAT": "1"})
