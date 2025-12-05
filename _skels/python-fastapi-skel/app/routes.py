from fastapi import APIRouter

from .example_items import routes as example_items_routes


router = APIRouter()
router.include_router(example_items_routes.router, tags=["example_items"], prefix="/example_items")