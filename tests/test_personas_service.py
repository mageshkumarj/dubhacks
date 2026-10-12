import json

import pytest

pytest.importorskip("pydantic")

from api.db import connect  # noqa: E402
from api.schemas.common import Envelope  # noqa: E402
from api.schemas.personas import Persona  # noqa: E402
from api.services import carts, personas  # noqa: E402
from api.services.store import MemoryStore  # noqa: E402


@pytest.fixture(scope="module")
def conn(sandbox_db):
    connection = connect(sandbox_db)
    yield connection
    connection.close()


def test_list_all_fifty_personas_and_filter_by_theme_and_kind(conn):
    everyone, total = personas.list_personas(conn, limit=100)
    assert total == 50 and len(everyone) == 50
    items, count = personas.list_personas(conn, theme="timekeeper", limit=100)
    assert count == 10 and {p["primary_theme"] for p in items} == {"timekeeper"}
    prospects, count = personas.list_personas(conn, kind="prospect", limit=100)
    assert count == 8 and all(p["account_id"] is None for p in prospects)


def test_theme_filter_includes_secondary_themes(conn):
    primary, _ = personas.list_personas(conn, theme="cart_whisperer", limit=100)
    with_secondary, total = personas.list_personas(conn, theme="cart_whisperer", include_secondary=True, limit=100)
    assert total > len(primary) and {"ACC-PERSONA-03"} <= {p["persona_id"] for p in with_secondary}


def test_pagination(conn):
    first, total = personas.list_personas(conn, limit=20, offset=0)
    second, _ = personas.list_personas(conn, limit=20, offset=20)
    assert total == 50 and not {p["persona_id"] for p in first} & {p["persona_id"] for p in second}


def test_persona_detail_matches_schema_and_includes_a_usable_cart(conn):
    persona = personas.get_persona(conn, "ACC-PERSONA-11")
    Persona.model_validate(persona)
    assert persona["kind"] == "customer" and persona["starting_cart"][0]["kind"] == "device"
    store = MemoryStore()
    cart_id = carts.create_cart(conn, store, persona["account_id"])["cart_id"]
    for item in persona["starting_cart"]:  # the cart comes ready to send to POST /v1/cart/{id}/items
        carts.add_item(conn, store, cart_id, **item)
    assert len(carts.get_cart(conn, store, cart_id)["items"]) == len(persona["starting_cart"])


def test_prospects_carry_stated_needs_and_no_account(conn):
    prospect = personas.get_persona(conn, "PROSPECT-04")
    Persona.model_validate(prospect)
    assert prospect["account_id"] is None and prospect["stated_lines"] == 4 and prospect["stated_usage"] == "heavy"


def test_unknown_persona_is_none(conn):
    assert personas.get_persona(conn, "PROSPECT-99") is None


def test_every_persona_validates_and_envelope_contract_holds(conn):
    for item in personas.list_personas(conn, limit=100)[0]:
        Persona.model_validate(item)
    from api.envelope import ok

    Envelope[list[Persona]].model_validate(ok(personas.list_personas(conn, limit=3)[0], {"total": 50}))


def test_personas_never_include_scoring_answers(conn):
    blob = json.dumps(personas.list_personas(conn, limit=100)[0]).lower()
    assert "churned" not in blob and "ground truth" not in blob
