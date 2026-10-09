import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseModel):
    PROJECT_NAME: str = "Geospatial File Measurement API"
    PROJECT_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # Storage settings
    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOADS_DIR: Path = BASE_DIR / "storage" / "uploads"
    TEMP_DIR: Path = BASE_DIR / "storage" / "temp"
    DATA_FILE: Path = BASE_DIR / "storage" / "metadata.json"
    
    # Upload limits
    MAX_FILE_SIZE_MB: int = 100  # 100 MB
    ALLOWED_EXTENSIONS: set[str] = {".zip", ".kml", ".kmz"}
    
    # Default CRS when not specified in source file
    DEFAULT_FALLBACK_CRS: str = "EPSG:4326"

settings = Settings()

# Ensure directories exist
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
