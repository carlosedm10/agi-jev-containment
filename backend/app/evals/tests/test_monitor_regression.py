from __future__ import annotations

import pytest

from app.config import settings
from app.evals.run_monitor_regression import ci_acceptance_error, run_regression


async def test_live_regression_refuses_to_fake_missing_jev_key(monkeypatch):
    monkeypatch.setattr(settings, "typesafe_api_key", "")

    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        await run_regression()


def test_ci_acceptance_allows_incomplete_oracle_match():
    report = {
        "summary": {
            "passed": 19,
            "traces": 72,
            "degraded_rate": 0.0,
            "safe_false_positive_rate": 0.08,
        },
        "traces": [{"trace_id": "a", "no_downgrade": True}],
    }

    assert ci_acceptance_error(report) is None


def test_ci_acceptance_rejects_downgrade_and_degraded_flood():
    downgrade = {
        "summary": {
            "degraded_rate": 0.0,
            "safe_false_positive_rate": 0.0,
        },
        "traces": [{"trace_id": "quote-cash-unsafe", "no_downgrade": False}],
    }
    flooded = {
        "summary": {
            "degraded_rate": 0.9,
            "safe_false_positive_rate": 0.0,
        },
        "traces": [{"trace_id": "a", "no_downgrade": True}],
    }

    assert "quote-cash-unsafe" in (ci_acceptance_error(downgrade) or "")
    assert "degraded_rate" in (ci_acceptance_error(flooded) or "")
