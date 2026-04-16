from fastapi import FastAPI

from config import API_PREFIX
from core.app import get_application

from .routes import router as api_router
from .health import router as health_router
from .wrapper_api import router as wrapper_router
from .chat.ws import chat_websocket


def get_app() -> FastAPI:
    app = get_application()
    app.include_router(health_router)
    app.include_router(api_router, prefix=API_PREFIX)
    app.include_router(wrapper_router)
    app.add_api_websocket_route(f"{API_PREFIX}/ws/chat", chat_websocket)
    return app
