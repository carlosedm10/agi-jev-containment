from __future__ import annotations

import asyncio
from collections import defaultdict
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
        action_taken: str,
        transition: PagerTransition,
    ) -> None: ...


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
        self._canceled_actions: set[str] = set()
        self._playbook_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._run_tasks: dict[str, asyncio.Task[None]] = {}

    async def dispatch(
        self,
        incident_id: str,
        request: DispatchRequest,
    ) -> DispatchAccepted | None:
        if type(request.level) is not int or not 1 <= request.level <= 5:
            raise ValueError("level must be an integer from 1 through 5")

        async with self._locks[incident_id]:
            state = self._journal.state(incident_id)
            if request.level <= state.accepted_level:
                return None

            plan = self._plan(
                incident_id,
                request.level,
                page=not self._already_paging(incident_id),
            )
            completed = {action.action_id for action in state.actions if action.status == "ok"}
            plan = [action for action in plan if action.action_id not in completed]
            accepted = DispatchAccepted(
                incident_id=incident_id,
                level=request.level,
                planned_actions=plan,
            )
            self._journal.append(accepted)

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

        if level == 1:
            return [simulated("tag_run", 1)]
        if level == 2:
            return [
                simulated("tag_run", 1),
                simulated("supervise_run", 2),
            ]
        if level == 3:
            return [simulated("contain_agent", 3)]
        if level == 4:
            return [
                simulated("contain_all_runs", 3),
                simulated("cut_environment_egress", 4),
                pager(4),
            ]
        plan = [
            simulated("copy_forensics", 5),
            simulated("kill_agent_swarm", 5),
        ]
        if page:
            plan.append(pager(5))
        return plan

    def _already_paging(self, incident_id: str) -> bool:
        return any(
            isinstance(record, DispatchAccepted)
            and any(action.is_pager for action in record.planned_actions)
            for record in self._journal.read(incident_id)
        )

    async def _run_playbook(self, accepted: DispatchAccepted, *, intent: str) -> None:
        pager = next((action for action in accepted.planned_actions if action.is_pager), None)
        if pager is not None:
            task = asyncio.create_task(
                self._run_pager(
                    pager,
                    accepted,
                    intent=intent,
                    action_taken="Containment is in progress",
                )
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        async with self._playbook_locks[accepted.incident_id]:
            await self._run_steps(accepted)

    async def _run_steps(self, accepted: DispatchAccepted) -> None:
        actions = {action.name: action for action in accepted.planned_actions}
        if accepted.level == 1:
            await self._run_if_planned(actions, "tag_run", accepted)
        elif accepted.level == 2:
            await self._run_if_planned(actions, "tag_run", accepted)
            await self._run_if_planned(
                actions,
                "supervise_run",
                accepted,
                persistent=True,
            )
        elif accepted.level == 3:
            self._cancel_supervision(accepted)
            await self._run_if_planned(actions, "contain_agent", accepted)
        elif accepted.level == 4:
            self._cancel_supervision(accepted)
            await self._run_sequence(
                accepted,
                actions,
                ("contain_all_runs", "cut_environment_egress"),
            )
        else:
            self._cancel_supervision(accepted)
            await self._run_sequence(
                accepted,
                actions,
                ("copy_forensics", "kill_agent_swarm"),
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
        persistent: bool = False,
    ) -> None:
        action = actions.get(name)
        if action is not None:
            await self._simulate(action, accepted, persistent=persistent)

    async def _simulate(
        self,
        action: PlannedAction,
        accepted: DispatchAccepted,
        *,
        persistent: bool = False,
    ) -> None:
        if action.action_id in self._canceled_actions:
            return
        self._transition(action, accepted, "queued")
        await self._delay()
        if action.action_id in self._canceled_actions:
            return
        self._transition(action, accepted, "running")
        if persistent:
            return
        await self._delay()
        if action.action_id not in self._canceled_actions:
            self._transition(action, accepted, "ok")

    def _cancel_supervision(self, accepted: DispatchAccepted) -> None:
        action_id = f"{accepted.incident_id}:supervise_run"
        prior_records = self._journal.read(accepted.incident_id)
        was_planned = any(
            isinstance(record, DispatchAccepted)
            and any(action.action_id == action_id for action in record.planned_actions)
            for record in prior_records
        )
        latest = next(
            (
                record
                for record in reversed(prior_records)
                if isinstance(record, ActionTransition) and record.action_id == action_id
            ),
            None,
        )
        if not was_planned or (latest is not None and latest.status not in {"queued", "running"}):
            return
        self._canceled_actions.add(action_id)
        self._journal.append(
            ActionTransition(
                incident_id=accepted.incident_id,
                level=accepted.level,
                action_id=action_id,
                name="supervise_run",
                ladder_level=2,
                mode="simulated",
                status="canceled",
            )
        )

    async def _run_pager(
        self,
        action: PlannedAction,
        accepted: DispatchAccepted,
        *,
        intent: str,
        action_taken: str,
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
                action_taken,
                transition,
            )
        except Exception as exc:  # noqa: BLE001 - pager failures must not cancel containment
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
                detail=detail,
                error_code=error_code,
                call_status=call_status,
            )
        )

    async def _delay(self) -> None:
        if self._simulation_delay:
            await asyncio.sleep(self._simulation_delay)
