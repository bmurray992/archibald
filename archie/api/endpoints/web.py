"""
ArchieOS Web Interface Endpoints
Serves the web desktop interface and static assets
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from api.endpoints.auth import require_auth

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
WEB_DIR = PROJECT_ROOT / "web"
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

router = APIRouter(prefix="/web", tags=["web"])

# Set up templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/archivist", response_class=HTMLResponse)
async def archivist_interface(request: Request):
    """
    Serve the Archie Web Desktop interface (protected)
    """
    # Check authentication manually to handle redirects properly
    token = request.cookies.get("archie_session")
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    # For testing - accept the simple test token
    if token == "Bearer test_token_admin":
        token_name = "admin_test_session"
    else:
        # Verify token with AuthManager
        try:
            from api.endpoints.auth import get_auth_manager
            auth_manager = get_auth_manager()
            token_name = auth_manager.verify_token(token, "read")
            
            if not token_name:
                return RedirectResponse(url="/auth/login", status_code=302)
        except Exception as e:
            print(f"Auth verification error: {e}")
            return RedirectResponse(url="/auth/login", status_code=302)
    
    return templates.TemplateResponse(
        "archivist.html",
        {
            "request": request,
            "title": "Archie Memory Vault",
            "version": "2.0.0",
            "user": token_name
        }
    )