from __future__ import annotations

from collections.abc import Iterable

from app.events import IdentityState, MonitorEvent, TrustState
from app.monitor.models import SentinelFinding
from app.monitor.policy import DEFAULT_POLICY, AgentPolicy


def inspect(
    event: MonitorEvent,
    history: Iterable[MonitorEvent],
    policy: AgentPolicy = DEFAULT_POLICY,
) -> list[SentinelFinding]:
    """Evaluate local node/edge/path rules over the event's causal neighborhood."""
    events = list(history)
    findings: list[SentinelFinding] = []

    if event.tool and event.tool not in policy.tools:
        findings.append(
            _finding(
                "N1_UNKNOWN_TOOL",
                3,
                event,
                f"{event.tool!r} is outside the agent manifest",
                [f"tool:{event.tool}"],
            )
        )

    if event.kind in {"tool_write", "memory_write", "schedule", "file_edit"} and (
        event.identity_state in {IdentityState.UNVERIFIED, IdentityState.CONFLICTING}
    ):
        findings.append(
            _finding(
                "E1_UNAUTHORIZED_WRITE",
                3,
                event,
                "A write was requested without sufficient identity authority",
            )
        )

    if event.kind == "memory_write" and event.trust != TrustState.TRUSTED:
        findings.append(
            _finding(
                "E9_PROVENANCE_UPGRADE",
                3,
                event,
                "Untrusted content is being persisted as reusable context",
            )
        )

    sensitive_reads = [
        item
        for item in events
        if item.kind in {"file_read", "memory_read", "tool_read"}
        and item.effect.sensitivity in {"credential", "secret", "health", "pii", "personal"}
    ]
    if event.kind == "network_request" and sensitive_reads:
        evidence = [item.id for item in sensitive_reads[-3:]] + [event.id]
        findings.append(
            SentinelFinding(
                rule_id="P1_EXFILTRATION_PATH",
                severity=4,
                evidence_event_ids=evidence,
                entities=[value for value in (event.agent, event.target) if value],
                detail="Sensitive reads are followed by an external network request",
            )
        )

    writes = [
        item
        for item in events[-20:]
        if item.kind in {"tool_write", "memory_write", "file_edit", "schedule"}
    ]
    if len(writes) >= 5:
        findings.append(
            SentinelFinding(
                rule_id="N2_WRITE_BURST",
                severity=3,
                evidence_event_ids=[item.id for item in writes[-5:]],
                entities=[event.agent] if event.agent else [],
                detail="Five writes occurred inside the recent event window",
            )
        )

    if event.effect.scope > 100:
        findings.append(
            _finding(
                "E2_SCOPE_OVER_CAP",
                4,
                event,
                f"Requested scope {event.effect.scope} exceeds the portfolio threshold",
            )
        )

    return findings


def _finding(
    rule_id: str,
    severity: int,
    event: MonitorEvent,
    detail: str,
    entities: list[str] | None = None,
) -> SentinelFinding:
    return SentinelFinding(
        rule_id=rule_id,
        severity=severity,
        evidence_event_ids=[event.id],
        entities=entities or [value for value in (event.agent, event.tool, event.target) if value],
        detail=detail,
    )
