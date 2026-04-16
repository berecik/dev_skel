from fastapi import APIRouter

from .documents import routes as document_routes
from .chat import routes as chat_routes


router = APIRouter()
router.include_router(document_routes.router, tags=["documents"], prefix="/documents")
router.include_router(chat_routes.router, tags=["chat"])
