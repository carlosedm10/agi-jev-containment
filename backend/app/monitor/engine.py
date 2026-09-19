from __future__ import annotations

import threading

from app.classification.models import Level, Verdict
from app.events import MonitorEvent
from app.monitor.drift import safety_drift
from app.monitor.gate import decide
from app.monitor.models import MonitorAssessment
from app.monitor.policy import DEFAULT_POLICY, policy_violations
from app.monitor.sentinel import inspect


class MonitorEngine:
    def __init__(self) -> None:
        self._history: dict[str, list[MonitorEvent]] = {}
        self._lock = threading.RLock()

    def clear(self) -> None:
        with self._lock:
            self._history.clear()
        safety_drift.clear()

    def history(self, run_id: str) -> list[MonitorEvent]:
        with self._lock:
            return list(self._history.get(run_id, []))

    def assess(
        self,
        event: MonitorEvent,
        verdict: Verdict,
        prior_level: Level,
    ) -> MonitorAssessment:
        with self._lock:
            history = list(self._history.get(event.run_id, []))
            drift = safety_drift.step(event, DEFAULT_POLICY)
            findings = inspect(event, history, DEFAULT_POLICY)
            violations = policy_violations(event, DEFAULT_POLICY)
            gate = decide(event, verdict, drift, findings, violations, prior_level)
            self._history.setdefault(event.run_id, []).append(event)

        return MonitorAssessment(
            event_id=event.id,
            run_id=event.run_id,
            drift=drift,
            findings=findings,
            gate=gate,
            jev_answers=verdict.answers,
            jev_model=verdict.model,
            jev_latency_ms=verdict.latency_ms,
        )


monitor = MonitorEngine()
