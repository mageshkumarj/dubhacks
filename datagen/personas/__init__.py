"""The 50 hackathon personas: 42 existing customers and 8 prospects, ten per theme."""

from .base import Persona, PersonaMeta
from .cart import CART
from .churn import CHURN
from .core import CORE
from .household import HOUSEHOLDS
from .matchmaker import MATCH
from .upgrade import UPGRADE

ALL: tuple[Persona, ...] = (*CORE, *CART, *MATCH, *CHURN, *UPGRADE, *HOUSEHOLDS)
PERSONAS = tuple(p.spec for p in sorted((p for p in ALL if p.spec), key=lambda p: p.spec.account_id))
PERSONA_IDS: tuple[str, ...] = tuple(spec.account_id for spec in PERSONAS)
PERSONA_META: tuple[PersonaMeta, ...] = tuple(sorted((p.meta for p in ALL), key=lambda m: m.persona_id))

__all__ = ["ALL", "PERSONAS", "PERSONA_IDS", "PERSONA_META", "Persona", "PersonaMeta"]
