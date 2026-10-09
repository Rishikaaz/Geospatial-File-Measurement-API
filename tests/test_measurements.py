import pyproj
from shapely.geometry import Polygon, LineString, Point
from app.services.measurement_service import MeasurementService
from app.services.crs_service import CRSService


def test_utm_epsg_determination():
    # Bangalore, India (approx lon 77.59, lat 12.97) -> Zone 43N (EPSG:32643)
    epsg_bengaluru = CRSService.calculate_utm_epsg(77.59, 12.97)
    assert epsg_bengaluru == 32643

    # San Francisco, USA (approx lon -122.41, lat 37.77) -> Zone 10N (EPSG:32610)
    epsg_sf = CRSService.calculate_utm_epsg(-122.41, 37.77)
    assert epsg_sf == 32610

    # Sydney, Australia (approx lon 151.20, lat -33.86) -> Zone 56S (EPSG:32756)
    epsg_sydney = CRSService.calculate_utm_epsg(151.20, -33.86)
    assert epsg_sydney == 32756


def test_polygon_measurement_with_geographic_crs():
    # 0.001 deg box (~111 meters x 108 meters near equator)
    coords = [(0.0, 0.0), (0.001, 0.0), (0.001, 0.001), (0.0, 0.001), (0.0, 0.0)]
    poly = Polygon(coords)
    wgs84 = pyproj.CRS.from_epsg(4326)

    detail = MeasurementService.calculate_measurement(poly, wgs84)
    assert detail.area is not None
    assert detail.area.sq_meters > 10000  # ~12,300 m²
    assert detail.area.sq_kilometers > 0.01
    assert detail.area.hectares > 1.0
    assert detail.length is None
    assert "EPSG:32631" in (detail.calculated_crs or "")


def test_linestring_measurement_with_geographic_crs():
    # ~11.1 km north-south line (0.1 degree lat)
    line = LineString([(0.0, 0.0), (0.0, 0.1)])
    wgs84 = pyproj.CRS.from_epsg(4326)

    detail = MeasurementService.calculate_measurement(line, wgs84)
    assert detail.length is not None
    assert 11000 < detail.length.meters < 11200
    assert 11.0 < detail.length.kilometers < 11.2
    assert detail.area is None


def test_point_measurement_handling():
    pt = Point(77.59, 12.97)
    wgs84 = pyproj.CRS.from_epsg(4326)

    detail = MeasurementService.calculate_measurement(pt, wgs84)
    assert detail.area is None
    assert detail.length is None
    assert "zero dimension" in (detail.measurement_note or "")


def test_polygon_with_hole_area():
    # Outer 100x100m, Inner hole 20x20m in projected meter CRS
    outer = [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]
    inner = [(40, 40), (60, 40), (60, 60), (40, 60), (40, 40)]
    poly = Polygon(shell=outer, holes=[inner])
    projected_crs = pyproj.CRS.from_epsg(3857)

    detail = MeasurementService.calculate_measurement(poly, projected_crs)
    assert detail.area is not None
    # 10,000 - 400 = 9,600 m²
    assert detail.area.sq_meters == 9600.0
