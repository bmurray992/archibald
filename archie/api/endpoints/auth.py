"""
Authentication endpoints for ArchieOS
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path

from archie_core.auth_manager import AuthManager

# Get template directory
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str
    rememberMe: bool = False


class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    redirect_url: Optional[str] = None


# Simple user store - in production, use a proper database
USERS = {
    "admin": {
        "password_hash": "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918",  # "admin"
        "permissions": ["read", "write", "delete"],
        "full_name": "Archive Administrator"
    },
    "user": {
        "password_hash": "04f8996da763b7a969b1028ee3007569eaf3a635486ddab211d512c85b9df8fb",  # "user"
        "permissions": ["read", "write"],
        "full_name": "Archive User"
    }
}


def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    return hash_password(password) == password_hash


def get_auth_manager() -> AuthManager:
    """Get auth manager instance"""
    return AuthManager()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display the login page"""
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(login_data: LoginRequest, response: Response):
    """Authenticate user and return session token"""
    
    try:
        # Check if user exists
        user_info = USERS.get(login_data.username)
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # Verify password
        if not verify_password(login_data.password, user_info["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # Create authentication token using AuthManager
        auth_manager = get_auth_manager()
        
        # Generate session token for this user
        session_token = auth_manager.create_token(
            name=f"{login_data.username}_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            permissions=user_info["permissions"],
            description=f"Web session for {user_info['full_name']}"
        )
        
        # Set session duration
        expires_delta = timedelta(days=30 if login_data.rememberMe else 1)
        expires = datetime.utcnow() + expires_delta
        
        # Set secure HTTP-only cookie
        response.set_cookie(
            key="archie_session",
            value=f"Bearer {session_token}",
            expires=expires,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )
        
        return LoginResponse(
            success=True,
            message="Login successful",
            token=f"Bearer {session_token}",
            redirect_url="/web/archivist"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")  # Debug logging
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/logout")
async def logout(response: Response):
    """Logout user and clear session"""
    
    # Clear the session cookie
    response.delete_cookie(key="archie_session")
    
    return {
        "success": True,
        "message": "Logged out successfully",
        "redirect_url": "/auth/login"
    }


@router.get("/check")
async def check_auth(request: Request):
    """Check if user is authenticated"""
    
    # Get token from cookie
    token = request.cookies.get("archie_session")
    if not token:
        return {"authenticated": False, "redirect": "/auth/login"}
    
    # For testing - accept the simple test token
    if token == "Bearer test_token_admin":
        return {
            "authenticated": True,
            "token_name": "admin_test_session",
            "permissions": ["read", "write", "delete"]
        }
    
    # Verify token with AuthManager
    try:
        auth_manager = get_auth_manager()
        token_name = auth_manager.verify_token(token, "read")
        
        if token_name:
            return {
                "authenticated": True,
                "token_name": token_name,
                "permissions": auth_manager.list_tokens().get(token_name, {}).get("permissions", [])
            }
        else:
            return {"authenticated": False, "redirect": "/auth/login"}
    except Exception as e:
        print(f"Auth check error: {e}")
        return {"authenticated": False, "redirect": "/auth/login"}


@router.post("/login-simple")
async def login_simple(login_data: LoginRequest, response: Response):
    """Simple login for testing"""
    
    # Just check basic credentials without AuthManager
    if login_data.username == "admin" and login_data.password == "admin":
        # Set a simple session cookie
        response.set_cookie(
            key="archie_session",
            value="Bearer test_token_admin",
            httponly=True,
            secure=False
        )
        
        return {
            "success": True,
            "message": "Login successful",
            "token": "Bearer test_token_admin"
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")


def require_auth(required_permission: str = "read"):
    """Dependency to require authentication for protected routes"""
    
    def auth_dependency(request: Request) -> str:
        # Get token from cookie or header
        token = request.cookies.get("archie_session")
        if not token:
            # Try Authorization header as fallback
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header
        
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # For testing - accept the simple test token
        if token == "Bearer test_token_admin":
            return "admin_test_session"
        
        # Verify token with AuthManager
        try:
            auth_manager = get_auth_manager()
            token_name = auth_manager.verify_token(token, required_permission)
            
            if not token_name:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            
            return token_name
        except Exception as e:
            print(f"Auth verification error: {e}")
            raise HTTPException(status_code=401, detail="Authentication verification failed")
    
    return auth_dependency