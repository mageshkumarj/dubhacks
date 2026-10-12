"""Commerce layer, read side: catalog, trade-in values and financing quotes."""

import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ..db import get_conn
from ..envelope import ok
from ..errors import not_found
from ..schemas.commerce import (
    SKU_PATTERN, Addon, Condition, Device, FinancingQuote, FinancingQuoteRequest, Plan, PromotionDefinition,
    TradeInPoint, TradeInValue,
)
from ..schemas.common import Envelope
from ..services import catalog, pricing
from .responses import ERROR_RESPONSES

router = APIRouter(prefix="/v1", tags=["commerce"], responses=ERROR_RESPONSES)

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]
Sku = Annotated[str, Path(pattern=SKU_PATTERN, description="e.g. TMO-STUB-DEV-0002")]


def _found[T](value: T | None, what: str) -> T:
    if value is None:
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return value


@router.get("/catalog/devices", response_model=Envelope[list[Device]], summary="Browse devices")
def list_devices(
    conn: Conn,
    tier: Annotated[str | None, Query(pattern=r"^[a-z_]{2,20}$")] = None,
    manufacturer: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
    status: Annotated[Literal["current", "legacy", "all"], Query(description="legacy = no longer sold")] = "current",
) -> dict:
    items, total = catalog.list_devices(conn, tier, manufacturer, limit, offset, None if status == "all" else status)
    return ok(items, {"total": total, "limit": limit, "offset": offset})


@router.get("/catalog/devices/{sku}", response_model=Envelope[Device], summary="One device")
def get_device(sku: Sku, conn: Conn) -> dict:
    return ok(_found(catalog.get_device(conn, sku), "Device"))


@router.get("/catalog/plans", response_model=Envelope[list[Plan]], summary="All plans")
def list_plans(conn: Conn) -> dict:
    return ok(catalog.list_plans(conn))


@router.get("/catalog/plans/{sku}", response_model=Envelope[Plan], summary="One plan")
def get_plan(sku: Sku, conn: Conn) -> dict:
    return ok(_found(catalog.get_plan(conn, sku), "Plan"))


@router.get("/catalog/addons", response_model=Envelope[list[Addon]], summary="Add-ons and accessories")
def list_addons(conn: Conn, kind: Annotated[str | None, Query(pattern=r"^[a-z_]{2,20}$")] = None) -> dict:
    return ok(catalog.list_addons(conn, kind))


@router.get("/catalog/promotions", response_model=Envelope[list[PromotionDefinition]], summary="Promotion rules")
def list_promotion_rules(
    conn: Conn,
    source: Annotated[Literal["site", "stub"] | None, Query(description="stub = invented retention offers")] = None,
) -> dict:
    return ok(catalog.list_promotions(conn, source))


@router.get("/tradein/value", response_model=Envelope[TradeInValue], summary="Trade-in value by age and condition")
def tradein_value(
    conn: Conn,
    device_sku: Annotated[str, Query(pattern=SKU_PATTERN)],
    age_months: Annotated[int, Query(ge=0, le=60)],
    condition: Condition = "good",
) -> dict:
    return ok(_found(pricing.tradein_value(conn, device_sku, age_months, condition), "Device"))


@router.get(
    "/tradein/curve/{sku}", response_model=Envelope[list[TradeInPoint]], summary="Trade-in value, 0-60 months"
)
def tradein_curve(sku: Sku, conn: Conn) -> dict:
    return ok(_found(pricing.tradein_curve(conn, sku), "Device"))


@router.post("/financing/quote", response_model=Envelope[FinancingQuote], summary="24/12/36-month installment quote")
def financing_quote(body: FinancingQuoteRequest, conn: Conn) -> dict:
    tier = body.credit_tier
    if tier is None and body.account_id:
        tier = pricing.credit_tier_for(conn, body.account_id)
        if tier is None:
            raise not_found("ACCOUNT_NOT_FOUND", "Account not found")
    quote = pricing.financing_quote(
        conn, body.device_sku, tier or "prime", body.term_months, body.down_payment_cents, body.tradein_credit_cents
    )
    return ok(_found(quote, "Device"))
