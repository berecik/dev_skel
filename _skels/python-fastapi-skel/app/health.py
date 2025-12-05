from fastapi import APIRouter
from fastapi_healthchecks.api.router import HealthcheckRouter, Probe

router = APIRouter()
### https://pypi.org/project/fastapi-healthchecks/
router.include_router(
    HealthcheckRouter(
        Probe(
            name="readiness",
            checks=[],
        ),
        Probe(
            name="liveness",
            checks=[],
        ),
    ),
    prefix="/health",
)