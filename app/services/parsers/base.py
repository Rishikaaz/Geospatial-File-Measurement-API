from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import pyproj
from shapely.geometry.base import BaseGeometry


@dataclass
class ExtractedFeature:
    feature_id: str | int
    geometry_type: str
    geometry: Optional[BaseGeometry]
    geojson_geometry: Optional[dict[str, Any]]
    properties: dict[str, Any] = field(default_factory=dict)
    crs: str = "EPSG:4326"


@dataclass
class ParsedGeospatialData:
    filename: str
    format: str
    crs: pyproj.CRS
    crs_name: str
    features: list[ExtractedFeature]
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseGeospatialParser(ABC):
    """Abstract interface for geospatial file parsers."""

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedGeospatialData:
        """Parse geospatial file and return extracted features and CRS metadata."""
        pass
