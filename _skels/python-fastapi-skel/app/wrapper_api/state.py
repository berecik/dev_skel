"""`/api/state` save/load endpoints for the React state-management layer.

The React skel's `src/state/state-api.ts` calls these to persist UI
slices (filters, sort order, preferences) per user across reloads.
The shape is intentionally opaque — the backend never parses
``value``, it just round-trips the string.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from fastapi import APIRouter
from sqlmodel import select

from .db import ReactState
from .deps import CurrentUser, SessionDep
from .schemas import ReactStateUpsert

router = APIRouter(prefix="/api/state", tags=["wrapper-state"])


@router.get("")
def load_state(session: SessionDep, user: CurrentUser) -> Dict[str, str]:
    rows = session.exec(
        select(ReactState).where(ReactState.user_id == user.id)
    ).all()
    return {row.key: row.value for row in rows}


@router.put("/{key}")
def upsert_state(
    key: str,
    payload: ReactStateUpsert,
    session: SessionDep,
    user: CurrentUser,
) -> Dict[str, str]:
    existing = session.exec(
        select(ReactState).where(
            (ReactState.user_id == user.id) & (ReactState.key == key)
        )
    ).first()
    if existing is None:
        existing = ReactState(user_id=user.id, key=key, value=payload.value)
    else:
        existing.value = payload.value
        existing.updated_at = datetime.utcnow()
    session.add(existing)
    session.commit()
    return {"key": key, "value": payload.value}


@router.delete("/{key}")
def delete_state(
    key: str,
    session: SessionDep,
    user: CurrentUser,
) -> Dict[str, object]:
    existing = session.exec(
        select(ReactState).where(
            (ReactState.user_id == user.id) & (ReactState.key == key)
        )
    ).first()
    deleted = False
    if existing is not None:
        session.delete(existing)
        session.commit()
        deleted = True
    return {"key": key, "deleted": deleted}
