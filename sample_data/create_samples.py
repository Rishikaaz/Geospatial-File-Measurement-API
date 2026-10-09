import os
import zipfile
from pathlib import Path
import shapefile

SAMPLE_DIR = Path(__file__).resolve().parent
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

def generate_sample_kml():
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Urban Survey &amp; Cadastre</name>
    <description>Sample dataset with agricultural parcels, roads, and survey benchmarks</description>
    
    <!-- Polygon 1: Agricultural Field Alpha -->
    <Placemark id="parcel_01">
      <name>Agri Parcel Alpha</name>
      <description>Rice cultivation sector A</description>
      <ExtendedData>
        <Data name="zone_type"><value>Agricultural</value></Data>
        <Data name="crop"><value>Basmati Rice</value></Data>
        <Data name="soil_type"><value>Alluvial</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5800,12.9700,0
              77.5850,12.9700,0
              77.5850,12.9750,0
              77.5800,12.9750,0
              77.5800,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>

    <!-- Polygon 2: Solar Park Beta (with internal exclusion hole) -->
    <Placemark id="parcel_02">
      <name>Solar Park Beta</name>
      <description>Renewable energy zone with substation exclusion zone</description>
      <ExtendedData>
        <Data name="zone_type"><value>Industrial/Solar</value></Data>
        <Data name="capacity_mw"><value>25</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5900,12.9700,0
              77.6000,12.9700,0
              77.6000,12.9800,0
              77.5900,12.9800,0
              77.5900,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
        <innerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5930,12.9730,0
              77.5970,12.9730,0
              77.5970,12.9770,0
              77.5930,12.9770,0
              77.5930,12.9730,0
            </coordinates>
          </LinearRing>
        </innerBoundaryIs>
      </Polygon>
    </Placemark>

    <!-- LineString 1: Main Highway Corridor -->
    <Placemark id="road_01">
      <name>East-West Expressway</name>
      <description>Four-lane arterial corridor</description>
      <ExtendedData>
        <Data name="road_class"><value>National Highway</value></Data>
        <Data name="lanes"><value>4</value></Data>
        <Data name="speed_limit"><value>80 km/h</value></Data>
      </ExtendedData>
      <LineString>
        <coordinates>
          77.5750,12.9650,0
          77.5850,12.9680,0
          77.5950,12.9720,0
          77.6050,12.9780,0
          77.6150,12.9850,0
        </coordinates>
      </LineString>
    </Placemark>

    <!-- LineString 2: Irrigation Canal -->
    <Placemark id="canal_01">
      <name>Feeder Canal Route 3</name>
      <description>Concrete lined canal</description>
      <ExtendedData>
        <Data name="type"><value>Irrigation Canal</value></Data>
        <Data name="flow_rate_cusecs"><value>120</value></Data>
      </ExtendedData>
      <LineString>
        <coordinates>
          77.5780,12.9800,0
          77.5830,12.9820,0
          77.5910,12.9860,0
          77.5980,12.9890,0
        </coordinates>
      </LineString>
    </Placemark>

    <!-- Point 1: Geodetic Survey Benchmark -->
    <Placemark id="pt_01">
      <name>Survey Benchmark BM-104</name>
      <description>High precision geodetic triangulation pillar</description>
      <ExtendedData>
        <Data name="elevation_m"><value>920.4</value></Data>
        <Data name="installed_year"><value>2021</value></Data>
      </ExtendedData>
      <Point>
        <coordinates>77.5950,12.9750,920.4</coordinates>
      </Point>
    </Placemark>

    <!-- Point 2: Weather Monitoring Station -->
    <Placemark id="pt_02">
      <name>Meteorological Station AWS-07</name>
      <description>Automated Weather Station</description>
      <Point>
        <coordinates>77.5820,12.9730,915.0</coordinates>
      </Point>
    </Placemark>

  </Document>
</kml>
"""
    kml_path = SAMPLE_DIR / "survey_dataset.kml"
    with open(kml_path, "w", encoding="utf-8") as f:
        f.write(kml_content)
    print(f"Generated sample KML: {kml_path}")


def generate_sample_shapefile_zip():
    # 1. Create temporary directory for shapefile components
    temp_shp_dir = SAMPLE_DIR / "temp_shp"
    temp_shp_dir.mkdir(exist_ok=True)
    base_name = temp_shp_dir / "cadastral_parcels"

    # Write WGS84 .prj file (WKT)
    prj_wkt = (
        'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
        'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
    )
    with open(f"{base_name}.prj", "w") as f:
        f.write(prj_wkt)

    # Create Shapefile with PyShp
    with shapefile.Writer(str(base_name), shapeType=shapefile.POLYGON) as w:
        w.field("NAME", "C", size=50)
        w.field("LAND_USE", "C", size=30)
        w.field("ASSESSED_V", "N", decimal=2)

        # Parcel A (Polygon)
        w.poly([[
            [-122.4200, 37.7700],
            [-122.4100, 37.7700],
            [-122.4100, 37.7800],
            [-122.4200, 37.7800],
            [-122.4200, 37.7700]
        ]])
        w.record("Mission District Lot 1", "Commercial", 4500000.00)

        # Parcel B (Polygon)
        w.poly([[
            [-122.4300, 37.7600],
            [-122.4220, 37.7600],
            [-122.4220, 37.7680],
            [-122.4300, 37.7680],
            [-122.4300, 37.7600]
        ]])
        w.record("Castro District Lot 4", "Residential", 2800000.00)

        # Parcel C (Polygon with hole)
        w.poly([
            [[-122.4050, 37.7850], [-122.3950, 37.7850], [-122.3950, 37.7950], [-122.4050, 37.7950], [-122.4050, 37.7850]],
            [[-122.4020, 37.7880], [-122.3980, 37.7880], [-122.3980, 37.7920], [-122.4020, 37.7920], [-122.4020, 37.7880]]
        ])
        w.record("SOMA Tech Hub", "Mixed-Use", 12500000.00)

    # Create Zip Archive
    zip_target = SAMPLE_DIR / "sample_parcels_shapefile.zip"
    with zipfile.ZipFile(zip_target, "w", zipfile.ZIP_DEFLATED) as z:
        for ext in [".shp", ".shx", ".dbf", ".prj"]:
            file_to_zip = temp_shp_dir / f"cadastral_parcels{ext}"
            if file_to_zip.exists():
                z.write(file_to_zip, arcname=f"cadastral_parcels{ext}")

    # Clean up temp
    import shutil
    shutil.rmtree(temp_shp_dir)
    print(f"Generated sample Shapefile zip: {zip_target}")


if __name__ == "__main__":
    generate_sample_kml()
    generate_sample_shapefile_zip()
