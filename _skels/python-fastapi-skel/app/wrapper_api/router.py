"""Single combined router for the wrapper-shared API."""

from __future__ import annotations

from fastapi import APIRouter

from .auth import router as auth_router
from .items import router as items_router
from .state import router as state_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(items_router)
router.include_router(state_router)
