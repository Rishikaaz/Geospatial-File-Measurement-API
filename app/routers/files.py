import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.models.schemas import (
    FileInfoResponse,
    MeasurementsResponse,
    GeoJSONFeatureCollectionResponse,
)
from app.services.file_storage import FileStorage
from app.services.processor import FileProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Geospatial Files & Measurements"])


@router.post(
    "/",
    response_model=FileInfoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload & Process Geospatial File",
    description="Uploads and processes a Shapefile (.zip) or KML/KMZ file, extracts features and computes measurements.",
)
async def upload_file(
    file: UploadFile = File(..., description="Geospatial file (.zip containing Shapefile, or .kml / .kmz)")
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty.",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed types are: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    try:
        content = await file.read()
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB.",
            )

        file_id, target_path = FileStorage.save_uploaded_file(file.filename, content)

        try:
            file_info, measurements = FileProcessor.process_file(
                file_id=file_id,
                file_path=target_path,
                original_filename=file.filename,
            )
            FileStorage.store_processed_result(file_id, file_info, measurements)
            return file_info

        except Exception as e:
            logger.error(f"Processing error for file '{file.filename}': {e}", exc_info=True)
            FileStorage.mark_failed(file_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Error processing geospatial file: {str(e)}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during file upload: {str(e)}",
        )


@router.get(
    "/",
    response_model=list[FileInfoResponse],
    summary="List Uploaded Files",
    description="Returns a list of all uploaded and processed geospatial files.",
)
def list_files():
    return FileStorage.list_all_files()


@router.get(
    "/{file_id}/",
    response_model=FileInfoResponse,
    summary="Get File Information",
    description="Returns metadata, feature count, CRS, and status for the specified file.",
)
def get_file_info(file_id: str):
    info = FileStorage.get_file_info(file_id)
    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found.",
        )
    return info


@router.get(
    "/{file_id}/measurements/",
    response_model=MeasurementsResponse,
    summary="Get File Measurements",
    description="Returns detailed measurement calculations (Area for Polygons, Length for LineStrings) for all features in the file.",
)
def get_file_measurements(
    file_id: str,
    geometry_type: Optional[str] = Query(
        None,
        description="Filter features by geometry type (e.g., Polygon, LineString, Point)",
    ),
    page: int = Query(1, ge=1, description="Page number for feature results"),
    limit: int = Query(100, ge=1, le=500, description="Number of feature measurements per page"),
):
    measurements = FileStorage.get_measurements(
        file_id=file_id,
        geometry_type=geometry_type,
        page=page,
        limit=limit,
    )
    if not measurements:
        info = FileStorage.get_file_info(file_id)
        if not info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File with ID '{file_id}' not found.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Measurements not available for file '{file_id}'. Status: {info.status}",
            )
    return measurements


@router.get(
    "/{file_id}/geojson/",
    response_model=GeoJSONFeatureCollectionResponse,
    summary="Export Features as GeoJSON",
    description="Exports the features with calculated measurement attributes in GeoJSON format for mapping and GIS tools.",
)
def get_file_geojson(file_id: str):
    geojson_data = FileStorage.get_geojson(file_id)
    if not geojson_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File or GeoJSON data for ID '{file_id}' not found.",
        )
    return JSONResponse(content=geojson_data)


@router.delete(
    "/{file_id}/",
    status_code=status.HTTP_200_OK,
    summary="Delete File",
    description="Deletes an uploaded file and all its associated measurement data.",
)
def delete_file(file_id: str):
    success = FileStorage.delete_file(file_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found.",
        )
    return {"message": f"File '{file_id}' successfully deleted."}
