import logging
from typing import Optional
import pyproj
from shapely.geometry.base import BaseGeometry
from shapely.geometry import (
    Polygon,
    MultiPolygon,
    LineString,
    MultiLineString,
    Point,
    MultiPoint,
    GeometryCollection,
)

from app.models.schemas import (
    AreaMeasurement,
    LengthMeasurement,
    MeasurementDetail,
)
from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)

SQ_METERS_TO_SQ_KM = 1e-6
SQ_METERS_TO_HECTARES = 1e-4
SQ_METERS_TO_ACRES = 0.00024710538146717
METERS_TO_KM = 0.001
METERS_TO_MILES = 0.00062137119223733
METERS_TO_FEET = 3.2808398950131


class MeasurementService:
    """Calculates geospatial measurements (Area for Polygons, Length for LineStrings)
    with accurate projected coordinate transformations.
    """

    @classmethod
    def calculate_measurement(
        cls, geometry: Optional[BaseGeometry], source_crs: pyproj.CRS
    ) -> MeasurementDetail:
        """Calculate measurement for any given geometry object.
        Gracefully handles all geometry types and unsupported or corrupted inputs.
        """
        if geometry is None or geometry.is_empty:
            return MeasurementDetail(
                method="none",
                measurement_note="Geometry is empty or null.",
            )

        geom_type = geometry.geom_type

        try:
            # 1. Polygon / MultiPolygon -> Calculate Area and Perimeter
            if isinstance(geometry, (Polygon, MultiPolygon)):
                return cls._calculate_polygon_measurement(geometry, source_crs)

            # 2. LineString / MultiLineString -> Calculate Length
            elif isinstance(geometry, (LineString, MultiLineString)):
                return cls._calculate_linestring_measurement(geometry, source_crs)

            # 3. Point / MultiPoint -> No measurement required
            elif isinstance(geometry, (Point, MultiPoint)):
                coords = []
                if isinstance(geometry, Point):
                    coords = [round(geometry.x, 6), round(geometry.y, 6)]
                else:
                    coords = [[round(p.x, 6), round(p.y, 6)] for p in geometry.geoms]
                return MeasurementDetail(
                    method="none",
                    measurement_note=f"Points have zero dimension (no area or length). Coordinates: {coords}",
                )

            # 4. GeometryCollection -> Aggregate parts or return note
            elif isinstance(geometry, GeometryCollection):
                return cls._calculate_collection_measurement(geometry, source_crs)

            # 5. Fallback for any unknown geometry type
            else:
                return MeasurementDetail(
                    method="unsupported",
                    measurement_note=f"Geometry type '{geom_type}' is not supported for area or length measurement.",
                )

        except Exception as e:
            logger.error(f"Error calculating measurement for {geom_type}: {e}", exc_info=True)
            return MeasurementDetail(
                method="error",
                measurement_note=f"Measurement calculation failed: {str(e)}",
            )

    @classmethod
    def _calculate_polygon_measurement(
        cls, polygon: Polygon | MultiPolygon, source_crs: pyproj.CRS
    ) -> MeasurementDetail:
        """Calculate projected area and perimeter for Polygon or MultiPolygon."""
        proj_crs, crs_name = CRSService.get_projected_crs_for_geometry(polygon, source_crs)
        projected_geom = CRSService.transform_geometry(polygon, source_crs, proj_crs)

        # Projected area in square meters
        area_m2 = float(projected_geom.area)
        perimeter_m = float(projected_geom.length)

        area_data = AreaMeasurement(
            sq_meters=round(area_m2, 4),
            sq_kilometers=round(area_m2 * SQ_METERS_TO_SQ_KM, 6),
            hectares=round(area_m2 * SQ_METERS_TO_HECTARES, 6),
            acres=round(area_m2 * SQ_METERS_TO_ACRES, 6),
            perimeter_meters=round(perimeter_m, 4),
            perimeter_kilometers=round(perimeter_m * METERS_TO_KM, 6),
        )

        return MeasurementDetail(
            area=area_data,
            length=None,
            calculated_crs=crs_name,
            method="planar_projected_utm" if source_crs.is_geographic else "direct_planar",
            measurement_note=None,
        )

    @classmethod
    def _calculate_linestring_measurement(
        cls, line: LineString | MultiLineString, source_crs: pyproj.CRS
    ) -> MeasurementDetail:
        """Calculate projected length for LineString or MultiLineString."""
        proj_crs, crs_name = CRSService.get_projected_crs_for_geometry(line, source_crs)
        projected_geom = CRSService.transform_geometry(line, source_crs, proj_crs)

        length_m = float(projected_geom.length)

        length_data = LengthMeasurement(
            meters=round(length_m, 4),
            kilometers=round(length_m * METERS_TO_KM, 6),
            miles=round(length_m * METERS_TO_MILES, 6),
            feet=round(length_m * METERS_TO_FEET, 4),
        )

        return MeasurementDetail(
            area=None,
            length=length_data,
            calculated_crs=crs_name,
            method="planar_projected_utm" if source_crs.is_geographic else "direct_planar",
            measurement_note=None,
        )

    @classmethod
    def _calculate_collection_measurement(
        cls, collection: GeometryCollection, source_crs: pyproj.CRS
    ) -> MeasurementDetail:
        """Calculate aggregate area and length from GeometryCollection items."""
        total_area = 0.0
        total_length = 0.0
        has_polygon = False
        has_line = False
        proj_crs, crs_name = CRSService.get_projected_crs_for_geometry(collection, source_crs)

        for sub_geom in collection.geoms:
            if isinstance(sub_geom, (Polygon, MultiPolygon)):
                proj_poly = CRSService.transform_geometry(sub_geom, source_crs, proj_crs)
                total_area += proj_poly.area
                has_polygon = True
            elif isinstance(sub_geom, (LineString, MultiLineString)):
                proj_line = CRSService.transform_geometry(sub_geom, source_crs, proj_crs)
                total_length += proj_line.length
                has_line = True

        area_obj = None
        if has_polygon:
            area_obj = AreaMeasurement(
                sq_meters=round(total_area, 4),
                sq_kilometers=round(total_area * SQ_METERS_TO_SQ_KM, 6),
                hectares=round(total_area * SQ_METERS_TO_HECTARES, 6),
                acres=round(total_area * SQ_METERS_TO_ACRES, 6),
            )

        length_obj = None
        if has_line:
            length_obj = LengthMeasurement(
                meters=round(total_length, 4),
                kilometers=round(total_length * METERS_TO_KM, 6),
                miles=round(total_length * METERS_TO_MILES, 6),
                feet=round(total_length * METERS_TO_FEET, 4),
            )

        return MeasurementDetail(
            area=area_obj,
            length=length_obj,
            calculated_crs=crs_name,
            method="planar_projected_utm" if source_crs.is_geographic else "direct_planar",
            measurement_note="Aggregated from GeometryCollection sub-geometries.",
        )
