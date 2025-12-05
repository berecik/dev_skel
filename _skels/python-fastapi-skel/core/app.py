from fastapi import FastAPI

from config import PROJECT_NAME, VERSION, CORE_API_PREFIX, USER_API_PREFIX, DEBUG
from core.users.routes.login import router as login_router
from core.users.routes.users import router as user_router
# from app.routes import router as api_router


def get_application() -> FastAPI:
    application = FastAPI(title=PROJECT_NAME, debug=DEBUG, version=VERSION)
    # application.include_router(api_router, prefix=API_PREFIX)
    application.include_router(user_router, tags=["users"], prefix=USER_API_PREFIX)
    application.include_router(login_router, tags=["login"], prefix=CORE_API_PREFIX)

    # pre_load = False
    # if pre_load:
    #     application.add_event_handler("startup", create_start_app_handler(application))
    return application
