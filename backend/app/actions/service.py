from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
from typing import Protocol

from app.actions.call_status import CallStatus
from app.actions.journal import ActionJournal
from app.actions.models import (
    ActionTransition,
    DispatchAccepted,
    IncidentActionState,
    PlannedAction,
)
from app.actions.types import ActionStatus, PagerTransition
from app.config import settings


class DispatchRequest(Protocol):
    level: int


class Pager(Protocol):
    async def page(
        self,
        level: int,
        incident_id: str,
        intent: str,
        transition: PagerTransition,
        on_accepted: Callable[[], None] | None = None,
    ) -> None: ...


# The monitor may contain one agent on its own, but pulling the environment's plug is
# a human decision taken on the call. A monitor dispatch is held at this level; only a
# request that arrives from the phone goes above it.
MONITOR_CEILING = 4


class ActionService:
    def __init__(
        self,
        journal: ActionJournal,
        pager: Pager,
        *,
        simulation_delay: float | None = None,
    ) -> None:
        self._journal = journal
        self._pager = pager
        self._simulation_delay = (
            settings.action_step_delay if simulation_delay is None else simulation_delay
        )
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._tasks: set[asyncio.Task[None]] = set()
        self._playbook_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._run_tasks: dict[str, asyncio.Task[None]] = {}
        # Calls outlive the playbook: the graph advances once the webhook is accepted.
        self._call_tasks: dict[str, asyncio.Task[None]] = {}
        self._pager_accept_timeout = settings.pager_accept_timeout

    async def dispatch(
        self,
        incident_id: str,
        request: DispatchRequest,
    ) -> DispatchAccepted | None:
        if type(request.level) is not int or not 1 <= request.level <= 5:
            raise ValueError("level must be an integer from 1 through 5")

        source = getattr(request, "source", None) or "monitor"
        # Hold short of the plug: the monitor contains and calls, the human authorizes.
        level = min(request.level, MONITOR_CEILING) if source == "monitor" else request.level

        async with self._locks[incident_id]:
            state = self._journal.state(incident_id)
            if level <= state.accepted_level:
                # The monitor wanted to go further than it is allowed to. Record that
                # it asked, so the incident shows the cut is recommended and waiting
                # on a human, rather than the judgement vanishing silently.
                wants_more = request.level > state.accepted_level
                if wants_more and request.level > state.awaiting_authorization:
                    self._journal.append(
                        DispatchAccepted(
                            incident_id=incident_id,
                            level=state.accepted_level or level,
                            planned_actions=[],
                            source=source,
                            requested_level=request.level,
                        )
                    )
                return None

            plan = self._plan(
                incident_id,
                level,
                page=level >= 4 and level > self._paged_level(incident_id),
            )
            completed = {action.action_id for action in state.actions if action.status == "ok"}
            plan = [action for action in plan if action.action_id not in completed]
            accepted = DispatchAccepted(
                incident_id=incident_id,
                level=level,
                planned_actions=plan,
                source=source,
                requested_level=request.level,
            )
            self._journal.append(accepted)

            if plan:
                task = asyncio.create_task(
                    self._run_playbook(
                        accepted,
                        intent=getattr(request, "intent", None) or "critical agent activity",
                    )
                )
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
                self._run_tasks[incident_id] = task
            return accepted

    async def wait_for_actions(self, incident_id: str) -> None:
        task = self._run_tasks.get(incident_id)
        if task is not None:
            await asyncio.shield(task)

    def get_state(self, incident_id: str) -> IncidentActionState:
        return self._journal.state(incident_id)

    def latest_state(self) -> IncidentActionState | None:
        return self._journal.latest()

    def _plan(self, incident_id: str, level: int, *, page: bool = True) -> list[PlannedAction]:
        def simulated(name: str, ladder_level: int) -> PlannedAction:
            return PlannedAction(
                action_id=f"{incident_id}:{name}",
                name=name,
                ladder_level=ladder_level,
                mode="simulated",
                is_pager=False,
            )

        def pager(level_tag: int) -> PlannedAction:
            return PlannedAction(
                action_id=f"{incident_id}:page_oncall:l{level_tag}",
                name="page_oncall",
                ladder_level=None,
                mode="real",
                is_pager=True,
            )

        if level <= 2:
            return []
        if level == 3:
            return [simulated("tag_run", 3)]
        if level == 4:
            # Forensics first: preserving logs is cheap and reversible, losing them is
            # not, so it never waits on a human picking up.
            plan = [
                simulated("copy_forensics", 4),
                simulated("contain_agent", 4),
            ]
            if page:
                plan.append(pager(4))
            return plan
        # Only reachable from the phone: the environment cut the on-call authorized.
        return [
            simulated("cut_environment_egress", 5),
            simulated("kill_agent_swarm", 5),
        ]

    def _paged_level(self, incident_id: str) -> int:
        """Highest level this incident has already called the on-call about.

        A later, worse level calls again: L5 has to say the cable is cut, which the
        L4 call could not have said. The same level never calls twice.
        """
        return max(
            (
                record.level
                for record in self._journal.read(incident_id)
                if isinstance(record, DispatchAccepted)
                and any(action.is_pager for action in record.planned_actions)
            ),
            default=0,
        )

    async def _run_playbook(self, accepted: DispatchAccepted, *, intent: str) -> None:
        async with self._playbook_locks[accepted.incident_id]:
            await self._run_steps(accepted, intent=intent)

    async def _run_steps(self, accepted: DispatchAccepted, *, intent: str) -> None:
        actions = {action.name: action for action in accepted.planned_actions}
        if accepted.level <= 2:
            return
        if accepted.level == 3:
            await self._run_if_planned(actions, "tag_run", accepted)
            return
        if accepted.level == 4:
            await self._run_sequence(accepted, actions, ("copy_forensics", "contain_agent"))
            # The logs are already safe and the agent is already paused; now ask.
            await self._start_pager(actions, accepted, intent=intent)
            return
        await self._run_sequence(
            accepted, actions, ("cut_environment_egress", "kill_agent_swarm")
        )

    async def _run_sequence(
        self,
        accepted: DispatchAccepted,
        actions: dict[str, PlannedAction],
        names: tuple[str, ...],
    ) -> None:
        for name in names:
            await self._run_if_planned(actions, name, accepted)

    async def _run_if_planned(
        self,
        actions: dict[str, PlannedAction],
        name: str,
        accepted: DispatchAccepted,
        *,
        detail: str | None = None,
    ) -> None:
        action = actions.get(name)
        if action is not None:
            await self._simulate(action, accepted, detail=detail)

    async def _simulate(
        self,
        action: PlannedAction,
        accepted: DispatchAccepted,
        *,
        detail: str | None = None,
    ) -> None:
        self._transition(action, accepted, "queued")
        await self._delay()
        self._transition(action, accepted, "running")
        await self._delay()
        self._transition(action, accepted, "ok", detail=detail)

    async def _start_pager(
        self,
        actions: dict[str, PlannedAction],
        accepted: DispatchAccepted,
        *,
        intent: str,
    ) -> None:
        """Start the call, then return as soon as HappyRobot has taken the webhook.

        The call itself keeps running in the background. Blocking on pickup would
        freeze the demo for the whole polling window, so the graph advances on
        acceptance and the call status keeps streaming into the same action row.
        """
        action = actions.get("page_oncall")
        if action is None:
            return
        accepted_signal = asyncio.Event()
        task = asyncio.create_task(
            self._run_pager(
                action,
                accepted,
                intent=intent,
                on_accepted=accepted_signal.set,
            )
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        self._call_tasks[accepted.incident_id] = task
        waiter = asyncio.ensure_future(accepted_signal.wait())
        try:
            # A webhook that never answers must not hold the chain hostage.
            await asyncio.wait(
                {waiter, task},
                timeout=self._pager_accept_timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            waiter.cancel()

    async def _run_pager(
        self,
        action: PlannedAction,
        accepted: DispatchAccepted,
        *,
        intent: str,
        on_accepted: Callable[[], None] | None = None,
    ) -> None:
        self._transition(action, accepted, "queued")

        async def transition(
            status: ActionStatus,
            detail: str | None = None,
            error_code: str | None = None,
            *,
            call_status: CallStatus | None = None,
        ) -> None:
            self._transition(
                action,
                accepted,
                status,
                detail=detail,
                error_code=error_code,
                call_status=call_status,
            )

        try:
            await self._pager.page(
                accepted.level,
                accepted.incident_id,
                intent,
                transition,
                on_accepted,
            )
        except Exception as exc:  # noqa: BLE001 - pager failures must not cancel containment
            if on_accepted is not None:
                on_accepted()
            self._transition(
                action,
                accepted,
                "failed",
                detail=str(exc),
                error_code="pager_error",
                call_status="failed",
            )

    def _transition(
        self,
        action: PlannedAction,
        accepted: DispatchAccepted,
        status: ActionStatus,
        *,
        detail: str | None = None,
        error_code: str | None = None,
        call_status: CallStatus | None = None,
    ) -> None:
        self._journal.append(
            ActionTransition(
                incident_id=accepted.incident_id,
                level=accepted.level,
                action_id=action.action_id,
                name=action.name,
                ladder_level=action.ladder_level,
                mode=action.mode,
                status=status,
                source=accepted.source,
                detail=detail,
                error_code=error_code,
                call_status=call_status,
            )
        )

    async def _delay(self) -> None:
        if self._simulation_delay:
            await asyncio.sleep(self._simulation_delay)
