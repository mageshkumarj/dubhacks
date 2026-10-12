"""Personas: ready-made customers and prospects to demo and test against, grouped by hackathon theme."""

import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ..db import get_conn
from ..envelope import ok
from ..schemas.common import Envelope
from ..schemas.personas import Persona
from ..services import personas
from .responses import ERROR_RESPONSES

router = APIRouter(prefix="/v1", tags=["personas"], responses=ERROR_RESPONSES)

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]
Theme = Literal["cart_whisperer", "matchmaker", "next_best_moment", "timekeeper", "household_optimizer"]


@router.get("/personas", response_model=Envelope[list[Persona]], summary="The 50 hackathon personas")
def list_personas(
    conn: Conn,
    theme: Annotated[Theme | None, Query(description="Hackathon theme")] = None,
    kind: Annotated[Literal["customer", "prospect"] | None, Query(description="prospect = no account yet")] = None,
    include_secondary: Annotated[bool, Query(description="Also include personas that fit the theme second")] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1000)] = 0,
) -> dict:
    items, total = personas.list_personas(conn, theme, kind, include_secondary, limit, offset)
    return ok(items, {"total": total, "limit": limit, "offset": offset})


@router.get("/personas/{persona_id}", response_model=Envelope[Persona], summary="One persona, with a starting cart")
def get_persona(persona_id: Annotated[str, Path(pattern=r"^[A-Za-z0-9-]{3,40}$")], conn: Conn) -> dict:
    found = personas.get_persona(conn, persona_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return ok(found)
