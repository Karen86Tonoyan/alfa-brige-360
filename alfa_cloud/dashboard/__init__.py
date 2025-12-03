"""
ALFA CLOUD Dashboard - Static file server
"""

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DASHBOARD_DIR = Path(__file__).parent


@router.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve dashboard HTML"""
    index_file = DASHBOARD_DIR / "index.html"
    return index_file.read_text(encoding="utf-8")


@router.get("/{filename}")
async def static_file(filename: str):
    """Serve static files"""
    file_path = DASHBOARD_DIR / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return {"error": "File not found"}
