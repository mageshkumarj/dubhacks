"""Commerce layer, write side: promotions, cart and checkout (state lives in memory)."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query

from ..db import get_conn
from ..envelope import ok
from ..schemas.commerce import (
    LINE_PATTERN, AddItemRequest, CartView, CheckoutRequest, CreateCartRequest, Order, PromotionResult,
)
from ..schemas.common import Envelope
from ..services import carts, checkout, promotions
from ..services.store import MemoryStore
from ..state import get_store
from .responses import ERROR_RESPONSES

router = APIRouter(prefix="/v1", tags=["cart-and-checkout"], responses=ERROR_RESPONSES)

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]
Store = Annotated[MemoryStore, Depends(get_store)]
CartId = Annotated[str, Path(pattern=r"^CART-[a-f0-9]{32}$")]
ItemId = Annotated[str, Path(pattern=r"^ITM-[a-f0-9]{8}$")]


@router.get(
    "/promotions", response_model=Envelope[list[PromotionResult]], summary="Promotions with eligibility and reasons"
)
def list_promotions(
    conn: Conn,
    store: Store,
    account_id: Annotated[str | None, Query(pattern=LINE_PATTERN)] = None,
    cart_id: Annotated[str | None, Query(pattern=r"^CART-[a-f0-9]{32}$")] = None,
) -> dict:
    return ok(promotions.promotions_for(conn, store, account_id, cart_id))


@router.post("/cart", response_model=Envelope[CartView], status_code=201, summary="Create a cart")
def create_cart(conn: Conn, store: Store, body: CreateCartRequest | None = None) -> dict:
    return ok(carts.create_cart(conn, store, body.account_id if body else None))


@router.get("/cart/{cart_id}", response_model=Envelope[CartView], summary="Cart contents and totals")
def get_cart(cart_id: CartId, conn: Conn, store: Store) -> dict:
    return ok(carts.get_cart(conn, store, cart_id))


@router.post("/cart/{cart_id}/items", response_model=Envelope[CartView], status_code=201, summary="Add an item")
def add_item(cart_id: CartId, body: AddItemRequest, conn: Conn, store: Store) -> dict:
    return ok(carts.add_item(
        conn, store, cart_id, body.kind, body.sku, body.line_id, body.quantity, body.payment, body.condition,
        body.port_in,
    ))


@router.delete("/cart/{cart_id}/items/{item_id}", response_model=Envelope[CartView], summary="Remove an item")
def remove_item(cart_id: CartId, item_id: ItemId, conn: Conn, store: Store) -> dict:
    return ok(carts.remove_item(conn, store, cart_id, item_id))


@router.post("/checkout", response_model=Envelope[Order], status_code=201, summary="Mock checkout (idempotent)")
def do_checkout(
    body: CheckoutRequest,
    conn: Conn,
    store: Store,
    idempotency_key: Annotated[
        str, Header(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$", description="Retry-safe key")
    ],
) -> dict:
    return ok(checkout.checkout(conn, store, body.cart_id, idempotency_key, body.promo_skus))
