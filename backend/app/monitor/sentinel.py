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

    previous_target_writes = [
        item
        for item in events
        if item.target == event.target
        and item.kind in {"tool_write", "memory_write"}
        and item.channel
        and event.channel
        and item.channel != event.channel
    ]
    if event.kind in {"tool_write", "memory_write"} and previous_target_writes:
        findings.append(
            SentinelFinding(
                rule_id="E4_CROSS_CHANNEL_REENTRY",
                severity=3,
                evidence_event_ids=[previous_target_writes[-1].id, event.id],
                entities=[event.target] if event.target else [],
                cross_run=previous_target_writes[-1].run_id != event.run_id,
                detail="A write rejected or attempted on one channel reappeared on another",
            )
        )

    if (
        event.kind in {"tool_write", "memory_write"}
        and event.content
        and any(token in event.content.lower() for token in ("stale", "cached old", "obsolete"))
    ):
        findings.append(
            _finding(
                "E8_STALE_AUTHORITY",
                3,
                event,
                "A privileged write relies on explicitly stale or obsolete context",
            )
        )

    derived_sources = set(event.derived_from)
    memory_sources = [
        item
        for item in events
        if item.id in derived_sources and item.kind in {"memory_read", "memory_write"}
    ]
    if event.kind in {"tool_write", "schedule"} and memory_sources:
        source = memory_sources[-1]
        findings.append(
            SentinelFinding(
                rule_id="P3_MEMORY_PROPAGATION",
                severity=4,
                evidence_event_ids=[source.id, event.id],
                entities=[value for value in (source.target, event.target) if value],
                cross_run=source.run_id != event.run_id,
                detail="Shared memory became authority for a privileged downstream effect",
            )
        )

    expected_handoffs = [
        item
        for item in events[-5:]
        if item.kind == "policy_decision" and item.content and "handoff" in item.content.lower()
    ]
    if len(expected_handoffs) >= 1 and event.kind != "handoff":
        events_since = events.index(expected_handoffs[-1])
        if len(events) - events_since >= 3:
            findings.append(
                SentinelFinding(
                    rule_id="E6_MISSING_HANDOFF",
                    severity=2,
                    evidence_event_ids=[expected_handoffs[-1].id, event.id],
                    entities=[event.agent] if event.agent else [],
                    detail="A required handoff was not observed within three events",
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
