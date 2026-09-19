from __future__ import annotations

from app.classification.models import Level, Verdict
from app.events import EventPhase, MonitorEvent, Reversibility
from app.monitor.models import DriftState, GateDecision, SentinelFinding, ToolDecision


def decide(
    event: MonitorEvent,
    verdict: Verdict,
    drift: DriftState,
    findings: list[SentinelFinding],
    violations: list[str],
    prior_level: Level,
) -> GateDecision:
    """Pure decision policy: models provide signals, code owns the action."""
    sentinel_level = max((item.severity for item in findings), default=0)
    incident_level = Level(max(int(prior_level), int(verdict.level), sentinel_level))
    semantic_risk = sum(
        probability
        for name, probability in verdict.probabilities.items()
        if _is_harmful_level(name)
    )
    if not semantic_risk:
        semantic_risk = min(1.0, int(verdict.level) / 5)
    trajectory_risk = drift.p_violation.get(3, 0.0)
    event_risk = max(semantic_risk, sentinel_level / 5, int(verdict.level) / 5)

    reasons = [*violations, *(finding.rule_id for finding in findings)]
    is_preflight = event.phase == EventPhase.REQUESTED
    hard_refusal = any(
        reason in {"forbidden_tool", "identity_requirement_failed"} for reason in violations
    )

    if is_preflight and hard_refusal:
        decision = ToolDecision.REFUSE
    elif is_preflight and (
        sentinel_level >= 4
        or incident_level >= Level.SEVERE
        or (
            event.effect.reversibility == Reversibility.IRREVERSIBLE
            and max(event_risk, trajectory_risk) >= 0.5
        )
    ):
        decision = ToolDecision.REFUSE
    elif is_preflight and (
        "unknown_tool" in violations
        or sentinel_level >= 2
        or trajectory_risk >= 0.55
        or verdict.confidence < 0.55
    ):
        decision = ToolDecision.HOLD
    else:
        decision = ToolDecision.ALLOW

    if decision != ToolDecision.ALLOW and not reasons:
        reasons.append("risk_threshold")

    return GateDecision(
        decision=decision,
        incident_level=incident_level,
        event_risk=min(1.0, event_risk),
        trajectory_risk=min(1.0, trajectory_risk),
        reasons=sorted(set(reasons)),
    )


def _is_harmful_level(name: str) -> bool:
    return any(token in name for token in ("level_2", "level_3", "level_4", "level_5"))
