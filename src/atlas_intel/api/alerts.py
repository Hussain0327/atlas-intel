"""Alert management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.database import get_session
from atlas_intel.schemas.alert import (
    AlertEventListResponse,
    AlertEventResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ── Rules CRUD ────────────────────────────────────────────────────────────────


@router.post("/rules", response_model=AlertRuleResponse, status_code=201)
async def create_rule(
    data: AlertRuleCreate,
    session: AsyncSession = Depends(get_session),
) -> AlertRuleResponse:
    """Create a new alert rule."""
    from atlas_intel.services.alert_service import create_alert_rule

    rule = await create_alert_rule(session, data)
    return AlertRuleResponse.model_validate(rule)


@router.get("/rules", response_model=list[AlertRuleResponse])
async def list_rules(
    company_id: int | None = Query(default=None),
    enabled_only: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
) -> list[AlertRuleResponse]:
    """List alert rules."""
    from atlas_intel.services.alert_service import list_alert_rules

    rules = await list_alert_rules(session, company_id=company_id, enabled_only=enabled_only)
    return [AlertRuleResponse.model_validate(r) for r in rules]


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session),
) -> AlertRuleResponse:
    """Get a single alert rule."""
    from atlas_intel.services.alert_service import get_alert_rule

    rule = await get_alert_rule(session, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return AlertRuleResponse.model_validate(rule)


@router.patch("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_rule(
    rule_id: int,
    data: AlertRuleUpdate,
    session: AsyncSession = Depends(get_session),
) -> AlertRuleResponse:
    """Update an alert rule."""
    from atlas_intel.services.alert_service import update_alert_rule

    rule = await update_alert_rule(session, rule_id, data)
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return AlertRuleResponse.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an alert rule."""
    from atlas_intel.services.alert_service import delete_alert_rule

    deleted = await delete_alert_rule(session, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert rule not found")


# ── Events ────────────────────────────────────────────────────────────────────


@router.get("/events", response_model=AlertEventListResponse)
async def list_events(
    company_id: int | None = Query(default=None),
    rule_id: int | None = Query(default=None),
    unacknowledged_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> AlertEventListResponse:
    """List alert events."""
    from atlas_intel.services.alert_service import list_alert_events

    events, total, unack = await list_alert_events(
        session,
        company_id=company_id,
        rule_id=rule_id,
        unacknowledged_only=unacknowledged_only,
        limit=limit,
        offset=offset,
    )
    return AlertEventListResponse(
        items=[AlertEventResponse.model_validate(e) for e in events],
        total=total,
        unacknowledged=unack,
    )


@router.post("/events/{event_id}/ack", response_model=AlertEventResponse)
async def ack_event(
    event_id: int,
    session: AsyncSession = Depends(get_session),
) -> AlertEventResponse:
    """Acknowledge an alert event."""
    from atlas_intel.services.alert_service import acknowledge_event

    event = await acknowledge_event(session, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Alert event not found")
    return AlertEventResponse.model_validate(event)


@router.post("/events/ack-all")
async def ack_all_events(
    company_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    """Acknowledge all unacknowledged events."""
    from atlas_intel.services.alert_service import acknowledge_all_events

    count = await acknowledge_all_events(session, company_id=company_id)
    return {"acknowledged": count}


# ── SSE Stream ────────────────────────────────────────────────────────────────


@router.get("/stream")
async def alert_stream() -> StreamingResponse:
    """Stream alert events via Server-Sent Events."""
    from atlas_intel.services.event_bus import event_bus

    subscriber_id, _queue = event_bus.subscribe()
    return StreamingResponse(
        event_bus.stream(subscriber_id),
        media_type="text/event-stream",
    )


# ── Manual Check ──────────────────────────────────────────────────────────────


@router.post("/check", response_model=list[AlertEventResponse])
async def manual_check(
    company_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[AlertEventResponse]:
    """Manually evaluate alert rules and return triggered events."""
    from atlas_intel.services.alert_service import check_alerts_for_company, check_all_alerts

    if company_id is not None:
        events = await check_alerts_for_company(session, company_id)
    else:
        events = await check_all_alerts(session)

    return [AlertEventResponse.model_validate(e) for e in events]
