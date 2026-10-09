import logging
from pathlib import Path
from typing import Optional

from app.models.schemas import (
    FeatureMeasurement,
    FileMeasurementSummary,
    MeasurementsResponse,
    FileInfoResponse,
    FileStatus,
)
from app.services.parsers.shapefile_parser import ShapefileZipParser
from app.services.parsers.kml_parser import KMLParser
from app.services.measurement_service import MeasurementService
from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)


class FileProcessor:
    """Orchestrates geospatial file parsing, feature extraction,
    and measurement computation.
    """

    @classmethod
    def process_file(cls, file_id: str, file_path: Path, original_filename: str) -> tuple[FileInfoResponse, MeasurementsResponse]:
        suffix = file_path.suffix.lower()

        # 1. Select parser based on file extension
        if suffix == ".zip":
            parser = ShapefileZipParser()
        elif suffix in [".kml", ".kmz"]:
            parser = KMLParser()
        else:
            raise ValueError(f"Unsupported file format: '{suffix}'. Only .zip (Shapefiles) and .kml / .kmz are supported.")

        # 2. Parse file and extract features
        parsed_data = parser.parse(file_path)

        # 3. Calculate measurements for each feature
        feature_measurements: list[FeatureMeasurement] = []
        polygon_count = 0
        linestring_count = 0
        point_count = 0
        other_count = 0
        total_area_m2 = 0.0
        total_length_m = 0.0
        geometry_types_set = set()

        for f in parsed_data.features:
            measurement = MeasurementService.calculate_measurement(f.geometry, parsed_data.crs)
            
            geom_type = f.geometry_type
            geometry_types_set.add(geom_type)

            if geom_type in ["Polygon", "MultiPolygon"]:
                polygon_count += 1
                if measurement.area:
                    total_area_m2 += measurement.area.sq_meters
            elif geom_type in ["LineString", "MultiLineString"]:
                linestring_count += 1
                if measurement.length:
                    total_length_m += measurement.length.meters
            elif geom_type in ["Point", "MultiPoint"]:
                point_count += 1
            else:
                other_count += 1

            feature_measurements.append(
                FeatureMeasurement(
                    feature_id=f.feature_id,
                    geometry_type=geom_type,
                    geometry=f.geojson_geometry,
                    crs=f.crs,
                    properties=f.properties,
                    measurement=measurement,
                )
            )

        # 4. Build summary
        summary = FileMeasurementSummary(
            total_features=len(feature_measurements),
            polygon_count=polygon_count,
            linestring_count=linestring_count,
            point_count=point_count,
            other_count=other_count,
            total_area_sq_meters=round(total_area_m2, 4),
            total_area_sq_km=round(total_area_m2 * 1e-6, 6),
            total_area_hectares=round(total_area_m2 * 1e-4, 6),
            total_area_acres=round(total_area_m2 * 0.000247105, 6),
            total_length_meters=round(total_length_m, 4),
            total_length_km=round(total_length_m * 0.001, 6),
        )

        file_size = file_path.stat().st_size if file_path.exists() else 0

        file_info = FileInfoResponse(
            id=file_id,
            filename=original_filename,
            feature_count=len(feature_measurements),
            crs=parsed_data.crs_name,
            status=FileStatus.COMPLETED,
            file_format=parsed_data.format,
            file_size_bytes=file_size,
            geometry_types=sorted(list(geometry_types_set)),
        )

        measurements_resp = MeasurementsResponse(
            file_id=file_id,
            filename=original_filename,
            source_crs=parsed_data.crs_name,
            status=FileStatus.COMPLETED,
            summary=summary,
            features=feature_measurements,
        )

        return file_info, measurements_resp
