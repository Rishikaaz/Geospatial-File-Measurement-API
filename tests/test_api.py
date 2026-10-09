from pathlib import Path
import pytest
from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Geospatial" in data["service"]


def test_upload_kml_file(client: TestClient, sample_kml_path: Path):
    with open(sample_kml_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("survey_dataset.kml", f, "application/vnd.google-earth.kml+xml")},
        )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "survey_dataset.kml"
    assert data["feature_count"] == 6
    assert data["status"] == "COMPLETED"
    assert "EPSG:4326" in data["crs"]

    file_id = data["id"]

    # 1. Test GET /api/files/{id}/
    info_resp = client.get(f"/api/files/{file_id}/")
    assert info_resp.status_code == 200
    assert info_resp.json()["id"] == file_id

    # 2. Test GET /api/files/{id}/measurements/
    measure_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert measure_resp.status_code == 200
    measure_data = measure_resp.json()
    assert measure_data["file_id"] == file_id
    assert measure_data["summary"]["total_features"] == 6
    assert measure_data["summary"]["polygon_count"] == 2
    assert measure_data["summary"]["linestring_count"] == 2
    assert measure_data["summary"]["point_count"] == 2
    assert measure_data["summary"]["total_area_sq_meters"] > 0
    assert measure_data["summary"]["total_length_meters"] > 0

    # 3. Test filter by geometry_type=Polygon
    poly_filter_resp = client.get(f"/api/files/{file_id}/measurements/?geometry_type=Polygon")
    assert poly_filter_resp.status_code == 200
    poly_data = poly_filter_resp.json()
    assert len(poly_data["features"]) == 2
    assert all(f["geometry_type"] == "Polygon" for f in poly_data["features"])

    # 4. Test GeoJSON export
    geojson_resp = client.get(f"/api/files/{file_id}/geojson/")
    assert geojson_resp.status_code == 200
    geojson = geojson_resp.json()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 6


def test_upload_shapefile_zip(client: TestClient, sample_shp_zip_path: Path):
    with open(sample_shp_zip_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("sample_parcels_shapefile.zip", f, "application/zip")},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "sample_parcels_shapefile.zip"
    assert data["feature_count"] == 3
    assert data["status"] == "COMPLETED"


def test_upload_invalid_extension(client: TestClient):
    response = client.post(
        "/api/files/",
        files={"file": ("test.txt", b"Hello World", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_get_nonexistent_file(client: TestClient):
    response = client.get("/api/files/nonexistent-id-999/")
    assert response.status_code == 404
