from fastapi import APIRouter
from fastapi_healthchecks.api.router import HealthcheckRouter, Probe

router = APIRouter()


@router.get("/api/health")
def health_check():
    """Simple health check endpoint — same path as all other skeletons."""
    return {"status": "ok"}


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