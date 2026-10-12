"""Building blocks for the 50 personas: 42 existing customers and 8 prospects (no account yet)."""

from dataclasses import dataclass

from .. import catalog
from ..rows import AccountSpec, LineSpec

PLAN = "TMO-STUB-PLAN-"
ADD = "TMO-STUB-ADD-"
SAVER, ESS, FOUR_LINE = PLAN + "ESSENTIALS-SAVER", PLAN + "ESSENTIALS", PLAN + "ESSENTIALS-4LINE"
MORE, BEYOND = PLAN + "MORE", PLAN + "BEYOND"
HINT, VIDEO = ADD + "HINT-BASIC", ADD + "STREAM-VIDEO"

CART_WHISPERER = "cart_whisperer"
MATCHMAKER = "matchmaker"
NEXT_BEST_MOMENT = "next_best_moment"
TIMEKEEPER = "timekeeper"
HOUSEHOLD = "household_optimizer"


def dev(name: str) -> str:
    return catalog.device_by_name(name).sku


@dataclass(frozen=True)
class PersonaMeta:
    persona_id: str
    account_id: str | None
    kind: str  # customer or prospect
    title: str
    primary_theme: str
    secondary_themes: tuple[str, ...]
    scenario: str
    stated_lines: int | None = None
    stated_budget_cents: int | None = None
    stated_usage: str | None = None
    stated_notes: str | None = None
    starting_cart: tuple[dict, ...] = ()
    related_account_id: str | None = None


@dataclass(frozen=True)
class Persona:
    spec: AccountSpec | None  # None for prospects
    meta: PersonaMeta


def _cart_item(number: int | None, item: dict) -> dict:
    """Turn {'device': 'iPhone 17', 'line': 1} style shorthand into the API's add-item fields."""
    out = {"kind": item["kind"]}
    if "device" in item:
        out["sku"] = dev(item["device"])
    if "plan" in item:
        out["sku"] = PLAN + item["plan"]
    if "addon" in item:
        out["sku"] = ADD + item["addon"]
    if "line" in item:
        out["line_id"] = f"LN-PERSONA-{number:02d}-{item['line']}"
    out.update({k: item[k] for k in ("quantity", "payment", "port_in", "condition") if k in item})
    return out


def customer(
    number: int, segment: str, tenure: int, unhappiness: float, lines: tuple[LineSpec, ...], note: str, *,
    title: str, theme: str, scenario: str, secondary: tuple[str, ...] = (), cart: tuple[dict, ...] = (),
    related: int | None = None, **spec_kwargs,
) -> Persona:
    account_id = f"ACC-PERSONA-{number:02d}"
    spec = AccountSpec(
        account_id=account_id, id_prefix=f"LN-PERSONA-{number:02d}", segment=segment, tenure_months=tenure,
        unhappiness=unhappiness, lines=lines, persona_note=note, plan_mismatch_rate=0.0,
        bill_spike_pct=spec_kwargs.pop("bill_spike_pct", 0.0), **spec_kwargs,
    )
    meta = PersonaMeta(
        persona_id=account_id, account_id=account_id, kind="customer", title=title, primary_theme=theme,
        secondary_themes=secondary, scenario=scenario,
        starting_cart=tuple(_cart_item(number, i) for i in cart),
        related_account_id=f"ACC-PERSONA-{related:02d}" if related else None,
    )
    return Persona(spec, meta)


def prospect(
    number: int, *, title: str, theme: str, scenario: str, lines: int, budget_dollars: int, usage: str, notes: str,
    secondary: tuple[str, ...] = (), cart: tuple[dict, ...] = (),
) -> Persona:
    meta = PersonaMeta(
        persona_id=f"PROSPECT-{number:02d}", account_id=None, kind="prospect", title=title, primary_theme=theme,
        secondary_themes=secondary, scenario=scenario, stated_lines=lines, stated_budget_cents=budget_dollars * 100,
        stated_usage=usage, stated_notes=notes, starting_cart=tuple(_cart_item(None, i) for i in cart),
    )
    return Persona(None, meta)
