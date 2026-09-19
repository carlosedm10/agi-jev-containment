from __future__ import annotations

from typing import Literal, Protocol

from app.actions.call_status import CallStatus

ActionStatus = Literal["queued", "running", "ok", "partial", "failed", "canceled"]


class PagerTransition(Protocol):
    async def __call__(
        self,
        status: ActionStatus,
        detail: str | None = None,
        error_code: str | None = None,
        *,
        call_status: CallStatus | None = None,
    ) -> None: ...
