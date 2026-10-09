import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import uuid

from app.config import settings
from app.models.schemas import (
    FileInfoResponse,
    MeasurementsResponse,
    FileStatus,
    FeatureMeasurement,
    GeoJSONFeatureCollectionResponse,
)

logger = logging.getLogger(__name__)


class FileStorage:
    """Thread-safe storage manager for uploaded geospatial files and their processed measurement data."""

    _lock = threading.Lock()
    _memory_cache: dict[str, dict[str, Any]] = {}
    _initialized: bool = False

    @classmethod
    def _init_storage(cls):
        if not cls._initialized:
            settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            if settings.DATA_FILE.exists():
                try:
                    with open(settings.DATA_FILE, "r", encoding="utf-8") as f:
                        cls._memory_cache = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not load existing metadata: {e}")
                    cls._memory_cache = {}
            cls._initialized = True

    @classmethod
    def _save_to_disk(cls):
        try:
            with open(settings.DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._memory_cache, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error persisting metadata to disk: {e}")

    @classmethod
    def save_uploaded_file(cls, filename: str, content: bytes) -> tuple[str, Path]:
        """Save uploaded file bytes to disk and return generated file_id and path."""
        cls._init_storage()
        file_id = str(uuid.uuid4().hex[:12])
        suffix = Path(filename).suffix.lower()
        saved_filename = f"{file_id}_{Path(filename).stem}{suffix}"
        target_path = settings.UPLOADS_DIR / saved_filename

        with open(target_path, "wb") as f:
            f.write(content)

        # Initial placeholder record
        with cls._lock:
            cls._memory_cache[file_id] = {
                "file_info": {
                    "id": file_id,
                    "filename": filename,
                    "feature_count": 0,
                    "crs": "Pending Detection",
                    "status": FileStatus.PENDING.value,
                    "file_size_bytes": len(content),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "file_path": str(target_path),
                },
                "measurements": None,
            }
            cls._save_to_disk()

        return file_id, target_path

    @classmethod
    def store_processed_result(
        cls,
        file_id: str,
        file_info: FileInfoResponse,
        measurements: MeasurementsResponse,
    ):
        """Store successfully processed file info and measurements."""
        cls._init_storage()
        with cls._lock:
            if file_id in cls._memory_cache:
                info_dict = file_info.model_dump()
                info_dict["created_at"] = cls._memory_cache[file_id]["file_info"].get(
                    "created_at", datetime.now(timezone.utc).isoformat()
                )
                info_dict["file_path"] = cls._memory_cache[file_id]["file_info"].get("file_path")
                cls._memory_cache[file_id] = {
                    "file_info": info_dict,
                    "measurements": measurements.model_dump(),
                }
                cls._save_to_disk()

    @classmethod
    def mark_failed(cls, file_id: str, error_message: str):
        """Mark a file processing task as failed."""
        cls._init_storage()
        with cls._lock:
            if file_id in cls._memory_cache:
                cls._memory_cache[file_id]["file_info"]["status"] = FileStatus.FAILED.value
                cls._memory_cache[file_id]["file_info"]["error_message"] = error_message
                cls._save_to_disk()

    @classmethod
    def get_file_info(cls, file_id: str) -> Optional[FileInfoResponse]:
        """Retrieve file information by ID."""
        cls._init_storage()
        record = cls._memory_cache.get(file_id)
        if not record:
            return None
        return FileInfoResponse(**record["file_info"])

    @classmethod
    def get_measurements(
        cls,
        file_id: str,
        geometry_type: Optional[str] = None,
        page: int = 1,
        limit: int = 100,
    ) -> Optional[MeasurementsResponse]:
        """Retrieve measurements for a file with optional geometry type filter and pagination."""
        cls._init_storage()
        record = cls._memory_cache.get(file_id)
        if not record or not record.get("measurements"):
            return None

        raw_measurements = record["measurements"]
        all_features = raw_measurements.get("features", [])

        # Apply geometry filter if provided
        if geometry_type:
            filtered = [
                f for f in all_features
                if f.get("geometry_type", "").lower() == geometry_type.lower()
            ]
        else:
            filtered = all_features

        # Pagination
        start = (page - 1) * limit
        end = start + limit
        paginated_features = filtered[start:end]

        response_dict = dict(raw_measurements)
        response_dict["features"] = paginated_features
        return MeasurementsResponse(**response_dict)

    @classmethod
    def get_geojson(cls, file_id: str) -> Optional[dict[str, Any]]:
        """Return features in standard GeoJSON FeatureCollection format with measurement attributes."""
        cls._init_storage()
        record = cls._memory_cache.get(file_id)
        if not record or not record.get("measurements"):
            return None

        measurements_data = record["measurements"]
        features_list = []

        for f in measurements_data.get("features", []):
            if f.get("geometry"):
                geojson_props = dict(f.get("properties", {}))
                geojson_props["feature_id"] = f.get("feature_id")
                geojson_props["geometry_type"] = f.get("geometry_type")
                geojson_props["measurement"] = f.get("measurement")
                
                features_list.append({
                    "type": "Feature",
                    "id": f.get("feature_id"),
                    "geometry": f.get("geometry"),
                    "properties": geojson_props,
                })

        return {
            "type": "FeatureCollection",
            "metadata": {
                "file_id": file_id,
                "filename": record["file_info"]["filename"],
                "crs": record["file_info"]["crs"],
                "total_features": len(features_list),
            },
            "features": features_list,
        }

    @classmethod
    def list_all_files(cls) -> list[FileInfoResponse]:
        """List all uploaded files."""
        cls._init_storage()
        return [
            FileInfoResponse(**data["file_info"])
            for data in cls._memory_cache.values()
        ]

    @classmethod
    def delete_file(cls, file_id: str) -> bool:
        """Delete file and its metadata."""
        cls._init_storage()
        with cls._lock:
            record = cls._memory_cache.pop(file_id, None)
            if not record:
                return False
            # Remove uploaded physical file if exists
            file_path = record["file_info"].get("file_path")
            if file_path:
                try:
                    p = Path(file_path)
                    if p.exists():
                        p.unlink()
                except Exception as e:
                    logger.warning(f"Error deleting file on disk: {e}")
            cls._save_to_disk()
            return True
