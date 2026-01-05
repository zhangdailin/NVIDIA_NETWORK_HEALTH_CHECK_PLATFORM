from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from api import router
import os
from datetime import datetime
from pathlib import Path

app = FastAPI(
    title="NVIDIA Network Health Check Platform",
    description="""
## NVIDIA InfiniBand Network Health Check Platform API

A comprehensive API for analyzing InfiniBand network diagnostics from IBDiagnet archives and UFM CSV files.

### Features

- **Health Score Analysis**: 0-100 score with severity classification
- **Network Topology Visualization**: Interactive HTML topology maps
- **Multi-dimensional Analysis**: BER, congestion, cable, and HCA diagnostics
- **Smart Insights**: Root cause analysis with recommendations

### Input Sources

- **IBDiagnet Archives**: `.zip` or `.tar.gz` files from UFM ibdiagnet tool
- **UFM CSV Files**: Generated via UFM REST API
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "upload",
            "description": "File upload endpoints for IBDiagnet archives and UFM CSV files"
        },
        {
            "name": "health",
            "description": "System health check endpoints"
        }
    ]
)

# CORS - configurable via environment variable
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8000,http://localhost:3000")
origins = [origin.strip() for origin in cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("results", exist_ok=True)

# Mount uploads directory to serve generated HTML files (like topo)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include API router
app.include_router(router, prefix="/api")

# Store startup time for health check
_startup_time = datetime.now()

# Frontend static files path (for production build)
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

@app.get("/api/health", tags=["health"])
def health_check():
    """
    Health check endpoint for monitoring and container orchestration.

    Returns:
        - status: Current service status
        - uptime_seconds: Time since service started
        - version: API version
    """
    uptime = datetime.now() - _startup_time
    return {
        "status": "healthy",
        "uptime_seconds": int(uptime.total_seconds()),
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


# Serve frontend static files in production
if FRONTEND_DIST.exists():
    # Mount static assets
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/", tags=["health"])
    async def serve_frontend():
        """Serve frontend index.html."""
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Serve SPA - return index.html for all non-API routes."""
        # Skip API and upload routes
        if full_path.startswith(("api/", "uploads/", "docs", "redoc", "openapi.json")):
            return {"detail": "Not Found"}

        # Check if it's a static file
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)

        # Return index.html for SPA routing
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/", tags=["health"])
    def read_root():
        """Root endpoint with welcome message (dev mode)."""
        return {
            "message": "NVIDIA Network Health Check Platform API",
            "docs": "/docs",
            "frontend": "Run 'npm run server' to start both frontend and backend"
        }
