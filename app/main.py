import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.config import settings
from app.routers import files_router, health_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="""
# 🌍 Geospatial File Measurement API

A high-performance backend service that accepts geospatial files (**Shapefiles** in `.zip` archives and **KML/KMZ** files), parses geographic and projected features, performs automatic **Coordinate Reference System (CRS) transformations** to optimal UTM projections, and calculates precise geometric measurements (**Area** for Polygons, **Length** for LineStrings).

## 🚀 Key Features
- **Format Support**: Shapefile (`.zip` with `.shp`, `.dbf`, `.shx`, `.prj`) and KML (`.kml`, `.kmz`).
- **Smart CRS Handling**: Automatically detects geographic coordinates (`EPSG:4326` / WGS84) and dynamically projects to optimal local UTM zones for distortion-free metric measurements.
- **Accurate Measurements**:
  - **Polygons & MultiPolygons**: Area in $m^2$, $km^2$, hectares, acres, and perimeter.
  - **LineStrings & MultiLineStrings**: Length in meters, kilometers, miles, feet.
  - **Points & MultiPoints**: Coordinates identified without dimensional distortion.
- **GeoJSON Export**: Complete GeoJSON FeatureCollection export with measurement attributes for Leaflet, Mapbox, QGIS, or ArcGIS.
- **Interactive UI**: Built-in visual dashboard for map visualization and instant measurement analysis.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware for open API access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(files_router, prefix=settings.API_PREFIX)
app.include_router(health_router, prefix=settings.API_PREFIX)

# Static files for visual dashboard
static_path = Path(__file__).resolve().parent / "static"
if static_path.exists():
    app.mount("/dashboard", StaticFiles(directory=str(static_path), html=True), name="static")


@app.get("/", include_in_schema=False)
def root():
    """Redirect root to interactive API documentation or dashboard."""
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
