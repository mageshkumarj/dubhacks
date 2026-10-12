"""Hackathon personas: ready-made customers and prospects for each theme."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class Persona(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_id: str
    account_id: str | None
    kind: str
    title: str
    primary_theme: str
    secondary_themes: list[str]
    scenario: str
    stated_lines: int | None
    stated_budget_cents: int | None
    stated_usage: str | None
    stated_notes: str | None
    starting_cart: list[dict[str, Any]]
    related_account_id: str | None
