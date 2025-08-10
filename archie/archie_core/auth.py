"""
ArchieOS Device-Based Authentication System
Implements device registration with public key authentication and capability tokens
"""
import os
import time
import jwt
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .db import Database
from .models import Device, DeviceRegisterRequest, DeviceTokenResponse

logger = logging.getLogger(__name__)

# Configuration from environment
SECRET_KEY = os.getenv("ARCHIE_SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ISS = os.getenv("ARCHIE_JWT_ISS", "archie.local")
JWT_EXP_DAYS = int(os.getenv("ARCHIE_JWT_EXP_DAYS", "30"))
DEVICE_ADMIN_EMAIL = os.getenv("ARCHIE_DEVICE_ADMIN_EMAIL", "admin@archie.local")

# Scopes
VALID_SCOPES = [
    "memory.read",
    "memory.write",
    "files.read",
    "files.write",
    "ingest.health",
    "ingest.email",
    "ingest.statement",
    "ingest.webclip",
    "admin.devices",
    "admin.jobs",
    "admin.system",
    "council.summon",
    "council.deliberate"
]

router = APIRouter(prefix="/api/auth", tags=["auth"])


class DeviceAuthManager:
    """Manages device registration and authentication"""
    
    def __init__(self):
        self.db = Database()
        self.db.initialize()
        
        # Auto-approve list (device names that don't need manual approval)
        self.auto_approve_devices = ["percy", "archie", "admin_device"]
    
    def verify_public_key(self, public_key_pem: str) -> bool:
        """Verify that a public key is valid"""
        try:
            # Load and validate the public key
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode(),
                backend=default_backend()
            )
            # Check if it's an RSA key with proper size
            if isinstance(public_key, rsa.RSAPublicKey):
                key_size = public_key.key_size
                return key_size >= 2048  # Minimum 2048 bits
            return False
        except Exception as e:
            logger.error(f"Invalid public key: {e}")
            return False
    
    def register_device(self, request: DeviceRegisterRequest) -> Dict[str, Any]:
        """Register a new device"""
        # Validate public key
        if not self.verify_public_key(request.public_key):
            raise HTTPException(status_code=400, detail="Invalid public key")
        
        # Validate scopes
        invalid_scopes = set(request.scopes) - set(VALID_SCOPES)
        if invalid_scopes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid scopes: {', '.join(invalid_scopes)}"
            )
        
        # Generate device ID
        device_id = str(uuid.uuid4())
        
        # Check if auto-approve
        approved_scopes = request.scopes
        if request.device_name not in self.auto_approve_devices:
            # For manual approval, grant limited scopes initially
            approved_scopes = ["memory.read", "files.read"]
            # TODO: Send approval request to DEVICE_ADMIN_EMAIL
            logger.info(f"Device {request.device_name} pending approval from {DEVICE_ADMIN_EMAIL}")
        
        # Store device in database
        device = {
            'id': device_id,
            'name': request.device_name,
            'public_key': request.public_key,
            'capabilities': approved_scopes,
            'device_type': request.device_type,
            'os_version': request.os_version,
            'app_version': request.app_version,
            'ip_address': None,  # Will be set on first use
            'council_member': self._identify_council_member(request.device_name)
        }
        
        self.db.register_device(device)
        
        # Generate JWT token
        token = self.generate_device_token(device_id, approved_scopes)
        
        return {
            'device_id': device_id,
            'token': token,
            'scopes': approved_scopes,
            'expires_at': datetime.utcnow() + timedelta(days=JWT_EXP_DAYS)
        }
    
    def generate_device_token(self, device_id: str, scopes: List[str]) -> str:
        """Generate a JWT token for a device"""
        exp = int(time.time()) + (JWT_EXP_DAYS * 86400)
        
        payload = {
            'sub': device_id,
            'scopes': scopes,
            'iss': JWT_ISS,
            'exp': exp,
            'iat': int(time.time()),
            'jti': str(uuid.uuid4())  # Token ID for revocation
        }
        
        return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    
    def verify_device_token(self, token: str, required_scope: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Verify a device token and optionally check scope"""
        try:
            # Decode token
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"], issuer=JWT_ISS)
            
            # Get device from database
            device = self.db.get_device(payload['sub'])
            if not device:
                logger.warning(f"Device {payload['sub']} not found")
                return None
            
            # Update last seen
            self.db.update_device_seen(payload['sub'])
            
            # Check required scope if provided
            if required_scope and required_scope not in payload.get('scopes', []):
                logger.warning(f"Device {device['name']} lacks required scope: {required_scope}")
                return None
            
            return {
                'device_id': payload['sub'],
                'device_name': device['name'],
                'scopes': payload['scopes'],
                'council_member': device.get('council_member')
            }
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    def renew_device_token(self, device_id: str) -> Optional[str]:
        """Renew a device's token"""
        device = self.db.get_device(device_id)
        if not device:
            return None
        
        return self.generate_device_token(device_id, device['capabilities'])
    
    def update_device_capabilities(self, device_id: str, capabilities: List[str]) -> bool:
        """Update device capabilities (admin only)"""
        device = self.db.get_device(device_id)
        if not device:
            return False
        
        # Validate capabilities
        invalid_scopes = set(capabilities) - set(VALID_SCOPES)
        if invalid_scopes:
            raise ValueError(f"Invalid scopes: {', '.join(invalid_scopes)}")
        
        # Update in database
        self.db.connection.execute(
            "UPDATE devices SET capabilities = ? WHERE id = ?",
            (jwt.dumps(capabilities), device_id)
        )
        
        return True
    
    def list_devices(self) -> List[Dict[str, Any]]:
        """List all registered devices"""
        cur = self.db.connection.execute(
            "SELECT * FROM devices ORDER BY last_seen DESC"
        )
        
        devices = []
        for row in cur:
            devices.append({
                'id': row['id'],
                'name': row['name'],
                'capabilities': jwt.loads(row['capabilities']),
                'last_seen': row['last_seen'],
                'device_type': row['device_type'],
                'os_version': row['os_version'],
                'app_version': row['app_version'],
                'council_member': row['council_member'],
                'status': 'active' if row['last_seen'] and 
                         (time.time() - row['last_seen']) < 86400 else 'inactive'
            })
        
        return devices
    
    def _identify_council_member(self, device_name: str) -> Optional[str]:
        """Identify which Council member a device belongs to"""
        name_lower = device_name.lower()
        
        if 'percy' in name_lower:
            return 'percy'
        elif 'archie' in name_lower:
            return 'archie'
        elif 'admin' in name_lower:
            return 'admin'
        
        # Future council members can be added here
        return None
    
    def verify_message_signature(self, 
                                device_id: str, 
                                message: bytes, 
                                signature: bytes) -> bool:
        """Verify a message was signed by a device's private key"""
        device = self.db.get_device(device_id)
        if not device:
            return False
        
        try:
            # Load public key
            public_key = serialization.load_pem_public_key(
                device['public_key'].encode(),
                backend=default_backend()
            )
            
            # Verify signature
            public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
            
        except InvalidSignature:
            return False
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False


# Global instance
_device_auth_manager = None


def get_device_auth_manager() -> DeviceAuthManager:
    """Get or create device auth manager instance"""
    global _device_auth_manager
    if _device_auth_manager is None:
        _device_auth_manager = DeviceAuthManager()
    return _device_auth_manager


# FastAPI dependencies

def require_device_auth(required_scope: Optional[str] = None):
    """Dependency for device authentication"""
    
    def auth_dependency(request: Request) -> Dict[str, Any]:
        # Get token from header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing authorization header")
        
        token = auth_header.replace("Bearer ", "")
        
        # Verify token
        auth_manager = get_device_auth_manager()
        device_info = auth_manager.verify_device_token(token, required_scope)
        
        if not device_info:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Update IP address if available
        client_ip = request.client.host if request.client else None
        if client_ip:
            auth_manager.db.update_device_seen(device_info['device_id'], client_ip)
        
        return device_info
    
    return auth_dependency


# API Routes

@router.post("/register_device", response_model=DeviceTokenResponse)
async def register_device(request: DeviceRegisterRequest):
    """Register a new device and get authentication token"""
    auth_manager = get_device_auth_manager()
    
    result = auth_manager.register_device(request)
    
    return DeviceTokenResponse(
        device_id=result['device_id'],
        token=result['token'],
        scopes=result['scopes'],
        expires_at=result['expires_at']
    )


@router.get("/renew")
async def renew_token(device_info: Dict[str, Any] = Depends(require_device_auth())):
    """Renew authentication token for current device"""
    auth_manager = get_device_auth_manager()
    
    new_token = auth_manager.renew_device_token(device_info['device_id'])
    if not new_token:
        raise HTTPException(status_code=400, detail="Failed to renew token")
    
    return {
        'token': new_token,
        'expires_at': datetime.utcnow() + timedelta(days=JWT_EXP_DAYS)
    }


@router.get("/devices", dependencies=[Depends(require_device_auth("admin.devices"))])
async def list_devices():
    """List all registered devices (admin only)"""
    auth_manager = get_device_auth_manager()
    return {
        'devices': auth_manager.list_devices()
    }


@router.post("/devices/{device_id}/capabilities")
async def update_device_capabilities(
    device_id: str,
    capabilities: List[str],
    device_info: Dict[str, Any] = Depends(require_device_auth("admin.devices"))
):
    """Update device capabilities (admin only)"""
    auth_manager = get_device_auth_manager()
    
    if auth_manager.update_device_capabilities(device_id, capabilities):
        return {'success': True, 'message': 'Capabilities updated'}
    else:
        raise HTTPException(status_code=404, detail="Device not found")


@router.post("/verify_signature")
async def verify_signature(
    message: str,
    signature: str,
    device_info: Dict[str, Any] = Depends(require_device_auth())
):
    """Verify a message signature from the authenticated device"""
    auth_manager = get_device_auth_manager()
    
    # Decode base64 signature
    import base64
    try:
        signature_bytes = base64.b64decode(signature)
        message_bytes = message.encode('utf-8')
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 encoding")
    
    if auth_manager.verify_message_signature(
        device_info['device_id'],
        message_bytes,
        signature_bytes
    ):
        return {'valid': True}
    else:
        return {'valid': False}


def register_auth_routes(app):
    """Register authentication routes with the FastAPI app"""
    app.include_router(router)