import os
import shutil
import tempfile
import zipfile
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any
import pyproj
import shapefile
from shapely.geometry import shape, mapping

from app.services.parsers.base import BaseGeospatialParser, ParsedGeospatialData, ExtractedFeature
from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)


class ShapefileZipParser(BaseGeospatialParser):
    """Parser for Shapefiles packaged within a .zip archive."""

    def parse(self, file_path: Path) -> ParsedGeospatialData:
        temp_dir = Path(tempfile.mkdtemp(prefix="shp_extract_"))
        try:
            # 1. Unzip the archive
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # 2. Locate .shp file (including subdirectories)
            shp_files = list(temp_dir.rglob("*.shp"))
            if not shp_files:
                raise ValueError("No .shp file found inside the uploaded zip archive.")

            shp_path = shp_files[0]
            base_stem = shp_path.stem

            # 3. Detect CRS from .prj file if available
            prj_files = list(shp_path.parent.glob(f"{base_stem}.prj")) + list(temp_dir.rglob("*.prj"))
            crs = pyproj.CRS.from_epsg(4326)
            crs_name = "EPSG:4326 (Default Assumed)"

            if prj_files:
                try:
                    with open(prj_files[0], "r", encoding="utf-8", errors="ignore") as prj_file:
                        prj_wkt = prj_file.read().strip()
                        if prj_wkt:
                            crs = CRSService.parse_crs(prj_wkt)
                            crs_name = CRSService.get_crs_name(crs)
                except Exception as e:
                    logger.warning(f"Error reading .prj file: {e}. Falling back to EPSG:4326.")

            # 4. Read features using pyshp
            features: list[ExtractedFeature] = []
            with shapefile.Reader(str(shp_path), encoding="utf-8", encodingErrors="ignore") as sf:
                for idx, shape_rec in enumerate(sf.shapeRecords()):
                    feature_id = idx + 1
                    geom = None
                    geojson_geom = None
                    geom_type = "Unknown"

                    try:
                        geo_dict = shape_rec.shape.__geo_interface__
                        geom_type = geo_dict.get("type", "Unknown")
                        if geo_dict.get("coordinates"):
                            geom = shape(geo_dict)
                            geojson_geom = geo_dict
                    except Exception as e:
                        logger.warning(f"Feature #{feature_id}: failed to parse shape: {e}")
                        geom_type = "Corrupted/Invalid"

                    # Parse attributes from DBF record
                    properties: dict[str, Any] = {}
                    try:
                        raw_dict = shape_rec.record.as_dict()
                        for k, v in raw_dict.items():
                            if isinstance(v, (datetime, date)):
                                properties[k] = v.isoformat()
                            elif isinstance(v, bytes):
                                properties[k] = v.decode("utf-8", errors="ignore")
                            else:
                                properties[k] = v
                    except Exception as e:
                        logger.warning(f"Feature #{feature_id}: failed to parse attributes: {e}")

                    features.append(
                        ExtractedFeature(
                            feature_id=feature_id,
                            geometry_type=geom_type,
                            geometry=geom,
                            geojson_geometry=geojson_geom,
                            properties=properties,
                            crs=crs_name,
                        )
                    )

            return ParsedGeospatialData(
                filename=file_path.name,
                format="Shapefile (.zip)",
                crs=crs,
                crs_name=crs_name,
                features=features,
                metadata={
                    "shape_count": len(features),
                    "shp_filename": shp_path.name,
                },
            )

        finally:
            # Clean up extracted temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
