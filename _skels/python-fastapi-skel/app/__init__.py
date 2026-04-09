from fastapi import FastAPI

from config import API_PREFIX
from core.app import get_application
# from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# from fastapi_events.handlers.local import local_handler
# from fastapi_events.middleware import EventHandlerASGIMiddleware

# from core.events import create_start_app_handler
from .routes import router as api_router
from .health import router as health_router
# Wrapper-shared API layer mounted at the ROOT (no /api/v1 prefix) so the
# React skeleton's `src/api/items.ts` and `src/state/state-api.ts` can
# call `${BACKEND_URL}/api/items`, `${BACKEND_URL}/api/auth/login`, etc.
# against this service exactly the same way they call the django-bolt
# backend. See `app/wrapper_api/__init__.py` for the full endpoint list.
from .wrapper_api import router as wrapper_router


def get_app() -> FastAPI:
    app = get_application()
    app.include_router(health_router)
    app.include_router(api_router, prefix=API_PREFIX)
    app.include_router(wrapper_router)
    # app.add_middleware(EventHandlerASGIMiddleware, handlers=[local_handler])
    # FastAPIInstrumentor.instrument_app(example_items)
    return app
