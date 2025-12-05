from fastapi import FastAPI

from config import API_PREFIX
from core.app import get_application
# from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# from fastapi_events.handlers.local import local_handler
# from fastapi_events.middleware import EventHandlerASGIMiddleware

# from core.events import create_start_app_handler
from .routes import router as api_router
from .health import router as health_router


def get_app() -> FastAPI:
    app = get_application()
    app.include_router(health_router)
    app.include_router(api_router, prefix=API_PREFIX)
    # app.add_middleware(EventHandlerASGIMiddleware, handlers=[local_handler])
    # FastAPIInstrumentor.instrument_app(example_items)
    return app
