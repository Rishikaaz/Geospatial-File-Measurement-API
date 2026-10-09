from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class FileStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AreaMeasurement(BaseModel):
    sq_meters: float = Field(..., description="Area in square meters (m²)")
    sq_kilometers: float = Field(..., description="Area in square kilometers (km²)")
    hectares: float = Field(..., description="Area in hectares (ha)")
    acres: float = Field(..., description="Area in acres")
    perimeter_meters: Optional[float] = Field(None, description="Perimeter in meters (m)")
    perimeter_kilometers: Optional[float] = Field(None, description="Perimeter in kilometers (km)")


class LengthMeasurement(BaseModel):
    meters: float = Field(..., description="Length in meters (m)")
    kilometers: float = Field(..., description="Length in kilometers (km)")
    miles: float = Field(..., description="Length in miles (mi)")
    feet: float = Field(..., description="Length in feet (ft)")


class MeasurementDetail(BaseModel):
    area: Optional[AreaMeasurement] = Field(None, description="Area calculations for Polygon/MultiPolygon geometries")
    length: Optional[LengthMeasurement] = Field(None, description="Length calculations for LineString/MultiLineString geometries")
    calculated_crs: Optional[str] = Field(None, description="Projected Coordinate Reference System used for measurement")
    method: str = Field(..., description="Calculation method (e.g., planar_projected_utm, geodesic, direct_planar)")
    measurement_note: Optional[str] = Field(None, description="Notes, e.g., for Point geometries or unprojectable shapes")


class FeatureGeoJSON(BaseModel):
    type: str = "Feature"
    id: Optional[str | int] = None
    geometry: Optional[dict[str, Any]] = None
    properties: dict[str, Any] = Field(default_factory=dict)


class FeatureMeasurement(BaseModel):
    feature_id: str | int = Field(..., description="Identifier or index of the feature")
    geometry_type: str = Field(..., description="Type of geometry (e.g. Polygon, LineString, Point)")
    geometry: Optional[dict[str, Any]] = Field(None, description="GeoJSON geometry representation")
    crs: str = Field(..., description="Original Feature Coordinate Reference System")
    properties: dict[str, Any] = Field(default_factory=dict, description="Feature attributes and metadata")
    measurement: MeasurementDetail = Field(..., description="Measurement calculations for this feature")


class FileMeasurementSummary(BaseModel):
    total_features: int = Field(0, description="Total number of features in file")
    polygon_count: int = Field(0, description="Count of Polygon and MultiPolygon features")
    linestring_count: int = Field(0, description="Count of LineString and MultiLineString features")
    point_count: int = Field(0, description="Count of Point and MultiPoint features")
    other_count: int = Field(0, description="Count of other or unsupported geometry features")
    total_area_sq_meters: float = Field(0.0, description="Sum of all polygon areas in m²")
    total_area_sq_km: float = Field(0.0, description="Sum of all polygon areas in km²")
    total_area_hectares: float = Field(0.0, description="Sum of all polygon areas in ha")
    total_area_acres: float = Field(0.0, description="Sum of all polygon areas in acres")
    total_length_meters: float = Field(0.0, description="Sum of all line lengths in meters")
    total_length_km: float = Field(0.0, description="Sum of all line lengths in kilometers")


class FileInfoResponse(BaseModel):
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original uploaded filename")
    feature_count: int = Field(..., description="Number of extracted geospatial features")
    crs: str = Field(..., description="Detected Coordinate Reference System")
    status: FileStatus = Field(..., description="File processing status")
    file_format: Optional[str] = Field(None, description="Detected format (e.g. Shapefile, KML)")
    file_size_bytes: Optional[int] = Field(None, description="Size of uploaded file in bytes")
    geometry_types: list[str] = Field(default_factory=list, description="Unique geometry types found in the file")
    created_at: Optional[str] = Field(None, description="Upload timestamp in ISO format")
    error_message: Optional[str] = Field(None, description="Error details if processing failed")


class MeasurementsResponse(BaseModel):
    file_id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original uploaded filename")
    source_crs: str = Field(..., description="Source Coordinate Reference System")
    status: FileStatus = Field(..., description="Processing status")
    summary: FileMeasurementSummary = Field(..., description="Aggregated summary of measurements")
    features: list[FeatureMeasurement] = Field(default_factory=list, description="List of feature measurements")


class GeoJSONFeatureCollectionResponse(BaseModel):
    type: str = "FeatureCollection"
    features: list[dict[str, Any]] = Field(default_factory=list)
    metadata: Optional[dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    supported_formats: list[str]
