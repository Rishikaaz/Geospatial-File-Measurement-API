from pathlib import Path
import pytest
from app.services.parsers.kml_parser import KMLParser
from app.services.parsers.shapefile_parser import ShapefileZipParser


def test_kml_parser_extracts_features(sample_kml_path: Path):
    assert sample_kml_path.exists(), "Sample KML file must exist"
    parser = KMLParser()
    data = parser.parse(sample_kml_path)

    assert data.format == "KML"
    assert data.crs_name == "EPSG:4326"
    assert len(data.features) == 6  # 2 polygons, 2 linestrings, 2 points

    geom_types = [f.geometry_type for f in data.features]
    assert "Polygon" in geom_types
    assert "LineString" in geom_types
    assert "Point" in geom_types

    # Verify attributes extracted
    poly_feature = next(f for f in data.features if f.geometry_type == "Polygon")
    assert poly_feature.properties.get("name") is not None
    assert poly_feature.geometry is not None


def test_shapefile_zip_parser_extracts_features(sample_shp_zip_path: Path):
    assert sample_shp_zip_path.exists(), "Sample Shapefile zip must exist"
    parser = ShapefileZipParser()
    data = parser.parse(sample_shp_zip_path)

    assert "Shapefile" in data.format
    assert len(data.features) == 3
    assert all(f.geometry_type in ["Polygon", "MultiPolygon"] for f in data.features)

    # Check DBF attribute preservation
    first_feat = data.features[0]
    assert "NAME" in first_feat.properties
    assert "LAND_USE" in first_feat.properties
