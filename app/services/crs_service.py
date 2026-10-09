import logging
from typing import Optional, Tuple
import pyproj
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

logger = logging.getLogger(__name__)


class CRSService:
    """Service to handle Coordinate Reference System (CRS) detection,
    validation, and dynamic UTM / planar projection transformations.
    """

    @staticmethod
    def parse_crs(crs_input: Optional[str]) -> pyproj.CRS:
        """Parse various CRS representations (EPSG strings, WKT, PROJ strings)
        into a valid pyproj.CRS object. Falls back to EPSG:4326 if unparseable.
        """
        if not crs_input:
            return pyproj.CRS.from_epsg(4326)

        cleaned = str(crs_input).strip()
        try:
            # Check if integer or standard EPSG:xxxx format
            if cleaned.isdigit():
                return pyproj.CRS.from_epsg(int(cleaned))
            return pyproj.CRS.from_user_input(cleaned)
        except Exception as e:
            logger.warning(f"Could not parse CRS '{crs_input}': {e}. Falling back to EPSG:4326.")
            return pyproj.CRS.from_epsg(4326)

    @staticmethod
    def get_crs_name(crs: pyproj.CRS) -> str:
        """Get standard readable name for a CRS (e.g. EPSG:4326 or WGS 84)."""
        try:
            auth = crs.to_authority()
            if auth:
                return f"{auth[0]}:{auth[1]}"
            if crs.to_epsg():
                return f"EPSG:{crs.to_epsg()}"
            return crs.name or "Unknown CRS"
        except Exception:
            return "EPSG:4326"

    @staticmethod
    def calculate_utm_epsg(lon: float, lat: float) -> int:
        """Determine appropriate EPSG code for WGS84 UTM Zone based on longitude and latitude.
        UTM zones span 6 degrees of longitude each (zones 1 to 60).
        """
        # Clamp longitude to [-180, 180]
        lon = max(-180.0, min(180.0, lon))
        lat = max(-80.0, min(84.0, lat))

        zone_number = int((lon + 180) / 6) + 1
        if zone_number > 60:
            zone_number = 60
        elif zone_number < 1:
            zone_number = 1

        if lat >= 0:
            return 32600 + zone_number  # WGS 84 / UTM zone XXN
        else:
            return 32700 + zone_number  # WGS 84 / UTM zone XXS

    @classmethod
    def get_projected_crs_for_geometry(
        cls, geometry: BaseGeometry, source_crs: pyproj.CRS
    ) -> Tuple[pyproj.CRS, str]:
        """Given a geometry and its source CRS, returns the most appropriate projected CRS
        suitable for accurate meter-based measurements (Area / Length).
        """
        if not source_crs.is_geographic:
            # Already a projected CRS (in meters, feet, etc.)
            crs_name = cls.get_crs_name(source_crs)
            return source_crs, f"{crs_name} (Source Projected CRS)"

        # For geographic coordinates (lat/lon in degrees), compute centroid to pick optimal UTM Zone
        try:
            centroid = geometry.centroid
            lon, lat = centroid.x, centroid.y
        except Exception:
            lon, lat = 0.0, 0.0

        utm_epsg = cls.calculate_utm_epsg(lon, lat)
        proj_crs = pyproj.CRS.from_epsg(utm_epsg)
        zone_str = f"EPSG:{utm_epsg} (UTM Zone {utm_epsg % 100}{'N' if utm_epsg < 32700 else 'S'})"
        return proj_crs, zone_str

    @classmethod
    def transform_geometry(
        cls, geometry: BaseGeometry, src_crs: pyproj.CRS, target_crs: pyproj.CRS
    ) -> BaseGeometry:
        """Transform a Shapely geometry from source CRS to target CRS."""
        if src_crs == target_crs:
            return geometry

        transformer = pyproj.Transformer.from_crs(src_crs, target_crs, always_xy=True)
        try:
            import numpy as np
            import shapely
            def _transform_coords(coords):
                tx, ty = transformer.transform(coords[:, 0], coords[:, 1])
                return np.column_stack((tx, ty))
            return shapely.transform(geometry, _transform_coords)
        except Exception:
            return transform(transformer.transform, geometry)
