"""Cart and order state. Immutable carts, replaced on every change; in memory, bounded, thread-safe.

The dataset is read-only, so carts and orders live here. Shared mode can provide another implementation
with the same methods (for example backed by a database).
"""

import copy
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, replace

MAX_CARTS = 5000
MAX_ORDERS = 5000


@dataclass(frozen=True)
class CartItem:
    item_id: str
    kind: str
    sku: str
    line_id: str | None = None
    quantity: int = 1
    payment: str = "financed"
    condition: str = "good"
    port_in: bool = False


@dataclass(frozen=True)
class Cart:
    cart_id: str
    account_id: str | None
    items: tuple[CartItem, ...] = ()
    status: str = "open"
    dataset_sha: str = ""

    def with_item(self, item: CartItem) -> "Cart":
        return replace(self, items=(*self.items, item))

    def without_item(self, item_id: str) -> "Cart":
        return replace(self, items=tuple(i for i in self.items if i.item_id != item_id))

    def closed(self) -> "Cart":
        return replace(self, status="checked_out")


def new_id(prefix: str, length: int) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:length]}"


class MemoryStore:
    def __init__(self, max_carts: int = MAX_CARTS, max_orders: int = MAX_ORDERS) -> None:
        self.lock = threading.RLock()
        self._max_carts, self._max_orders = max_carts, max_orders
        self._carts: OrderedDict[str, Cart] = OrderedDict()
        self._orders: OrderedDict[tuple[str, str], tuple[tuple, dict]] = OrderedDict()
        self._traded_in: set[str] = set()

    def create(self, account_id: str | None, dataset_sha: str = "") -> Cart:
        cart = Cart(new_id("CART", 32), account_id, dataset_sha=dataset_sha)
        with self.lock:
            self._carts[cart.cart_id] = cart
            while len(self._carts) > self._max_carts:
                self._carts.popitem(last=False)
        return cart

    def get(self, cart_id: str) -> Cart | None:
        with self.lock:
            cart = self._carts.get(cart_id)
            if cart is not None:
                self._carts.move_to_end(cart_id)
            return cart

    def save(self, cart: Cart) -> None:
        with self.lock:
            if cart.cart_id in self._carts:
                self._carts[cart.cart_id] = cart
                self._carts.move_to_end(cart.cart_id)

    def get_order(self, cart_id: str, idempotency_key: str) -> tuple[tuple, dict] | None:
        """Keys are scoped to a cart, so callers cannot collide with or probe each other's keys.

        Returns (request fingerprint, order copy). Keys are remembered for the last MAX_ORDERS orders.
        """
        with self.lock:
            found = self._orders.get((cart_id, idempotency_key))
            return None if found is None else (found[0], copy.deepcopy(found[1]))

    def save_order(self, cart_id: str, idempotency_key: str, fingerprint: tuple, order: dict) -> None:
        with self.lock:
            self._orders[(cart_id, idempotency_key)] = (fingerprint, copy.deepcopy(order))
            while len(self._orders) > self._max_orders:
                self._orders.popitem(last=False)

    def is_traded_in(self, line_id: str) -> bool:
        with self.lock:
            return line_id in self._traded_in

    def mark_traded_in(self, line_ids: list[str]) -> None:
        with self.lock:
            self._traded_in.update(line_ids)
