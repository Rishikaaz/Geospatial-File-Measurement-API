import logging
import tempfile
import zipfile
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional, List
import pyproj
from shapely.geometry import (
    Point,
    LineString,
    Polygon,
    MultiPolygon,
    MultiLineString,
    MultiPoint,
    GeometryCollection,
    mapping,
)
from shapely.geometry.base import BaseGeometry

from app.services.parsers.base import BaseGeospatialParser, ParsedGeospatialData, ExtractedFeature

logger = logging.getLogger(__name__)


class KMLParser(BaseGeospatialParser):
    """Parser for KML (.kml) and compressed KMZ (.kmz) files."""

    # Common KML XML namespaces
    NAMESPACES = {
        "kml22": "http://www.opengis.net/kml/2.2",
        "kml21": "http://earth.google.com/kml/2.1",
        "kml20": "http://earth.google.com/kml/2.0",
        "gx": "http://www.google.com/kml/ext/2.2",
    }

    def parse(self, file_path: Path) -> ParsedGeospatialData:
        is_kmz = file_path.suffix.lower() == ".kmz"
        temp_dir = None

        try:
            kml_content: str = ""
            if is_kmz:
                temp_dir = Path(tempfile.mkdtemp(prefix="kmz_extract_"))
                with zipfile.ZipFile(file_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)
                kml_files = list(temp_dir.rglob("*.kml"))
                if not kml_files:
                    raise ValueError("No .kml file found inside the KMZ archive.")
                with open(kml_files[0], "r", encoding="utf-8", errors="ignore") as f:
                    kml_content = f.read()
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    kml_content = f.read()

            features = self._parse_kml_xml(kml_content)

            crs = pyproj.CRS.from_epsg(4326)
            crs_name = "EPSG:4326"

            return ParsedGeospatialData(
                filename=file_path.name,
                format="KMZ" if is_kmz else "KML",
                crs=crs,
                crs_name=crs_name,
                features=features,
                metadata={
                    "placemark_count": len(features),
                    "crs_standard": "OGC KML 2.2 (WGS84)",
                },
            )
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _parse_kml_xml(self, kml_text: str) -> list[ExtractedFeature]:
        features: list[ExtractedFeature] = []
        if not kml_text.strip():
            return features

        try:
            # Preprocess unescaped ampersands that are not standard XML entities
            import re
            cleaned_text = re.sub(r"&(?!(amp|lt|gt|apos|quot|#\d+|#x[0-9a-fA-F]+);)", "&amp;", kml_text)
            tree = ET.fromstring(cleaned_text)
            # Remove namespace prefixes from tags for simpler iteration
            for elem in tree.iter():
                if "}" in elem.tag:
                    elem.tag = elem.tag.split("}", 1)[1]

            placemark_elements = list(tree.iter("Placemark"))

            for idx, pm in enumerate(placemark_elements):
                feature_id = pm.attrib.get("id") or (idx + 1)
                
                # Extract Placemark properties / metadata
                props: dict[str, Any] = {}
                name_elem = pm.find("name")
                if name_elem is not None and name_elem.text:
                    props["name"] = name_elem.text.strip()

                desc_elem = pm.find("description")
                if desc_elem is not None and desc_elem.text:
                    props["description"] = desc_elem.text.strip()

                # ExtendedData
                ext_data = pm.find("ExtendedData")
                if ext_data is not None:
                    for data_el in ext_data.iter("Data"):
                        name = data_el.attrib.get("name")
                        val_el = data_el.find("value")
                        if name and val_el is not None and val_el.text:
                            props[name] = val_el.text.strip()

                    for simple_el in ext_data.iter("SimpleData"):
                        name = simple_el.attrib.get("name")
                        if name and simple_el.text:
                            props[name] = simple_el.text.strip()

                # Extract Geometry
                geom, geom_type = self._extract_geometry_from_element(pm)

                geojson_geom = None
                if geom:
                    try:
                        geojson_geom = mapping(geom)
                    except Exception:
                        pass

                features.append(
                    ExtractedFeature(
                        feature_id=str(feature_id),
                        geometry_type=geom_type,
                        geometry=geom,
                        geojson_geometry=geojson_geom,
                        properties=props,
                        crs="EPSG:4326",
                    )
                )

        except Exception as e:
            logger.error(f"Error parsing KML XML: {e}", exc_info=True)
            raise ValueError(f"Failed to parse KML content: {str(e)}")

        return features

    def _extract_geometry_from_element(self, element: ET.Element) -> tuple[Optional[BaseGeometry], str]:
        # 1. Polygon
        polygon_elem = element.find(".//Polygon")
        if polygon_elem is not None:
            poly = self._parse_polygon(polygon_elem)
            if poly:
                return poly, "Polygon"

        # 2. LineString
        line_elem = element.find(".//LineString")
        if line_elem is not None:
            line = self._parse_linestring(line_elem)
            if line:
                return line, "LineString"

        # 3. Point
        point_elem = element.find(".//Point")
        if point_elem is not None:
            pt = self._parse_point(point_elem)
            if pt:
                return pt, "Point"

        # 4. MultiGeometry
        multi_elem = element.find(".//MultiGeometry")
        if multi_elem is not None:
            geoms = []
            for child in multi_elem:
                tag = child.tag
                if tag == "Polygon":
                    p = self._parse_polygon(child)
                    if p: geoms.append(p)
                elif tag == "LineString":
                    l = self._parse_linestring(child)
                    if l: geoms.append(l)
                elif tag == "Point":
                    pt = self._parse_point(child)
                    if pt: geoms.append(pt)
            
            if geoms:
                if all(isinstance(g, Polygon) for g in geoms):
                    return MultiPolygon(geoms), "MultiPolygon"
                elif all(isinstance(g, LineString) for g in geoms):
                    return MultiLineString(geoms), "MultiLineString"
                elif all(isinstance(g, Point) for g in geoms):
                    return MultiPoint(geoms), "MultiPoint"
                return GeometryCollection(geoms), "GeometryCollection"

        return None, "Unknown"

    def _parse_coordinates(self, coord_str: Optional[str]) -> List[tuple[float, float]]:
        """Parse coordinate string 'lon,lat,alt lon,lat,alt' into tuples (lon, lat)."""
        if not coord_str:
            return []
        coords = []
        tokens = coord_str.strip().split()
        for token in tokens:
            parts = token.split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    coords.append((lon, lat))
                except ValueError:
                    continue
        return coords

    def _parse_point(self, point_elem: ET.Element) -> Optional[Point]:
        coord_elem = point_elem.find("coordinates")
        if coord_elem is not None and coord_elem.text:
            coords = self._parse_coordinates(coord_elem.text)
            if coords:
                return Point(coords[0])
        return None

    def _parse_linestring(self, line_elem: ET.Element) -> Optional[LineString]:
        coord_elem = line_elem.find("coordinates")
        if coord_elem is not None and coord_elem.text:
            coords = self._parse_coordinates(coord_elem.text)
            if len(coords) >= 2:
                return LineString(coords)
        return None

    def _parse_polygon(self, poly_elem: ET.Element) -> Optional[Polygon]:
        outer_elem = poly_elem.find(".//outerBoundaryIs//coordinates")
        if outer_elem is None or not outer_elem.text:
            return None
        outer_coords = self._parse_coordinates(outer_elem.text)
        if len(outer_coords) < 3:
            return None

        # Handle inner boundary holes
        holes = []
        for inner_elem in poly_elem.findall(".//innerBoundaryIs//coordinates"):
            if inner_elem.text:
                inner_coords = self._parse_coordinates(inner_elem.text)
                if len(inner_coords) >= 3:
                    holes.append(inner_coords)

        return Polygon(shell=outer_coords, holes=holes if holes else None)
