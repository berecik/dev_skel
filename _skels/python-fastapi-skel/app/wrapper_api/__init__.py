"""Wrapper-shared API layer.

The dev_skel React frontend (`ts-react-skel`) calls a fixed set of
endpoints on whichever backend is named by the wrapper-shared
``BACKEND_URL`` env var:

* ``POST /api/auth/register`` — `{username, email, password, password_confirm}`
* ``POST /api/auth/login`` — `{username, password}` → `{access, refresh, user_id, username}`
* ``GET / POST /api/items`` — list / create wrapper-shared items
* ``GET /api/items/{id}`` — retrieve a single item
* ``POST /api/items/{id}/complete`` — mark complete (matches the React
  `useItems` hook)
* ``GET /api/state`` — load every UI state slice for the current user
* ``PUT /api/state/{key}`` — upsert a slice
* ``DELETE /api/state/{key}`` — drop a slice

This module exposes a single `router` that mounts all of the above at
the root of the FastAPI app (no `/api/v1` prefix), so the React skel
talks to FastAPI exactly the same way it talks to the django-bolt skel.
The endpoints sign and verify JWTs against the wrapper-shared
``settings.JWT_SECRET`` so a token issued by this service is
interchangeable with one issued by any other backend in the wrapper.
"""

from .router import router

__all__ = ["router"]
