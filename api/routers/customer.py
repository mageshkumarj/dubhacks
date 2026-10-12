"""Customer and context layer: household structure, aggregated context, and history."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ..db import get_conn
from ..envelope import ok
from ..schemas.common import Envelope
from ..schemas.customer import (
    AccountSummary, BillingMonth, CustomerContext, Household, SupportInteraction, UsageMonth,
)
from ..services import accounts, context, history
from .responses import ERROR_RESPONSES

router = APIRouter(prefix="/v1", tags=["customer"], responses=ERROR_RESPONSES)

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]
AccountId = Annotated[str, Path(pattern=r"^[A-Za-z0-9-]{3,40}$", description="e.g. ACC-PERSONA-02")]
LineId = Annotated[str | None, Query(pattern=r"^[A-Za-z0-9-]{3,40}$")]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0, le=100_000)]


def _found(value, what: str):
    if value is None:
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return value


@router.get("/accounts", response_model=Envelope[list[AccountSummary]], summary="List accounts (households)")
def list_accounts(
    conn: Conn,
    segment: Annotated[str | None, Query(pattern=r"^[a-z_]{2,20}$")] = None,
    persona_only: Annotated[bool, Query(description="Only the 10 curated demo accounts")] = False,
    limit: Limit = 50,
    offset: Offset = 0,
) -> dict:
    items, total = accounts.list_accounts(conn, segment, persona_only, limit, offset)
    return ok(items, {"total": total, "limit": limit, "offset": offset})


@router.get("/households/{account_id}", response_model=Envelope[Household], summary="Household structure")
def get_household(account_id: AccountId, conn: Conn) -> dict:
    return ok(_found(accounts.get_household(conn, account_id), "Household"))


@router.get(
    "/customers/{account_id}/context",
    response_model=Envelope[CustomerContext],
    summary="Aggregated live context for one customer",
)
def get_context(account_id: AccountId, conn: Conn) -> dict:
    return ok(_found(context.get_context(conn, account_id), "Customer"))


@router.get("/customers/{account_id}/usage", response_model=Envelope[list[UsageMonth]], summary="Monthly usage")
def get_usage(
    account_id: AccountId,
    conn: Conn,
    line_id: LineId = None,
    months: Annotated[int, Query(ge=1, le=12)] = 12,
) -> dict:
    return ok(_found(history.get_usage(conn, account_id, line_id, months), "Account or line"))


@router.get("/customers/{account_id}/billing", response_model=Envelope[list[BillingMonth]], summary="Billing history")
def get_billing(account_id: AccountId, conn: Conn) -> dict:
    return ok(_found(history.get_billing(conn, account_id), "Customer"))


@router.get(
    "/customers/{account_id}/support-interactions",
    response_model=Envelope[list[SupportInteraction]],
    summary="Recent support interactions, newest first",
)
def get_support(account_id: AccountId, conn: Conn, limit: Limit = 50) -> dict:
    return ok(_found(history.get_support_interactions(conn, account_id, limit), "Customer"))
