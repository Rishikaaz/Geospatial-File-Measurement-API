import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.main import app

from app.services.file_storage import FileStorage
from app.config import settings

@pytest.fixture(scope="session")
def client():
    return TestClient(app)

@pytest.fixture(scope="session")
def sample_kml_path():
    return Path(__file__).resolve().parent.parent / "sample_data" / "survey_dataset.kml"

@pytest.fixture(scope="session")
def sample_shp_zip_path():
    return Path(__file__).resolve().parent.parent / "sample_data" / "sample_parcels_shapefile.zip"
