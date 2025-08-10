"""
ArchieOS Authentication Middleware
"""
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from archie_core.auth_manager import AuthManager

# Security scheme
security = HTTPBearer()

# Global auth manager instance
auth_manager = None


def get_auth_manager() -> AuthManager:
    """Get or create auth manager instance"""
    global auth_manager
    if auth_manager is None:
        auth_manager = AuthManager()
    return auth_manager


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_mgr: AuthManager = Depends(get_auth_manager)
) -> str:
    """
    Verify Bearer token and return token name
    """
    if not credentials:
        raise HTTPException(
            status_code=403,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = f"Bearer {credentials.credentials}"
    token_name = auth_mgr.verify_token(token, "read")
    
    if not token_name:
        raise HTTPException(
            status_code=403,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_name


async def require_write_permission(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_mgr: AuthManager = Depends(get_auth_manager)
) -> str:
    """
    Verify token has write permission
    """
    if not credentials:
        raise HTTPException(
            status_code=403,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = f"Bearer {credentials.credentials}"
    token_name = auth_mgr.verify_token(token, "write")
    
    if not token_name:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions - write access required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_name


async def require_delete_permission(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_mgr: AuthManager = Depends(get_auth_manager)
) -> str:
    """
    Verify token has delete permission
    """
    if not credentials:
        raise HTTPException(
            status_code=403,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = f"Bearer {credentials.credentials}"
    token_name = auth_mgr.verify_token(token, "delete")
    
    if not token_name:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions - delete access required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_name


async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_mgr: AuthManager = Depends(get_auth_manager)
) -> Optional[str]:
    """
    Optional authentication - returns token name if provided, None otherwise
    """
    if not credentials:
        return None
    
    token = f"Bearer {credentials.credentials}"
    return auth_mgr.verify_token(token, "read")