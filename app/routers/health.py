from fastapi import APIRouter
from app.config import settings
from app.models.schemas import HealthResponse

router = APIRouter(tags=["Health & Status"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns the operational status, version, and supported file formats.",
)
def health_check():
    return HealthResponse(
        status="healthy",
        service=settings.PROJECT_NAME,
        version=settings.PROJECT_VERSION,
        supported_formats=sorted(list(settings.ALLOWED_EXTENSIONS)),
    )
