"""
ArchieOS Authentication Manager - Secure access control for the storage OS
"""
import os
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class AuthManager:
    """
    Manages authentication tokens and access control for ArchieOS
    """
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            base_dir = Path(__file__).parent.parent
            config_path = base_dir / "config" / "auth_tokens.json"
        
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Default token from environment or generate
        self.default_token = os.getenv("ARCHIE_TOKEN", self._generate_token())
        
        self._init_auth_store()
        logger.info("🔐 Archie: Authentication system initialized - vault is secure!")
    
    def _init_auth_store(self):
        """Initialize the authentication token store"""
        if not self.config_path.exists():
            default_tokens = {
                "tokens": {
                    "percy": {
                        "token_hash": self._hash_token(self.default_token),
                        "permissions": ["read", "write", "delete"],
                        "created_at": datetime.now().isoformat(),
                        "last_used": None,
                        "active": True,
                        "description": "Percy's primary access token"
                    }
                },
                "settings": {
                    "token_expiry_hours": 8760,  # 1 year
                    "max_failed_attempts": 5,
                    "lockdown_duration_minutes": 15
                }
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(default_tokens, f, indent=2)
            
            # Save default token for reference (in production, share this securely)
            token_file = self.config_path.parent / ".default_token"
            with open(token_file, 'w') as f:
                f.write(f"ARCHIE_TOKEN={self.default_token}\n")
            
            logger.info(f"📝 Default token saved to {token_file}")
    
    def verify_token(self, token: str, required_permission: str = "read") -> Optional[str]:
        """
        Verify a token and check permissions
        Returns the token name if valid, None otherwise
        """
        if not token or not token.startswith("Bearer "):
            return None
        
        actual_token = token.replace("Bearer ", "")
        token_hash = self._hash_token(actual_token)
        
        # Load current tokens
        with open(self.config_path, 'r') as f:
            auth_data = json.load(f)
        
        # Check each registered token
        for token_name, token_info in auth_data["tokens"].items():
            if not token_info.get("active", False):
                continue
                
            if token_info["token_hash"] == token_hash:
                # Check permissions
                if required_permission not in token_info.get("permissions", []):
                    logger.warning(f"🚫 Token {token_name} lacks {required_permission} permission")
                    return None
                
                # Update last used
                token_info["last_used"] = datetime.now().isoformat()
                
                # Save updated auth data
                with open(self.config_path, 'w') as f:
                    json.dump(auth_data, f, indent=2)
                
                logger.info(f"✅ Authenticated: {token_name}")
                return token_name
        
        logger.warning("🚫 Invalid token attempted")
        return None
    
    def create_token(self, 
                    name: str, 
                    permissions: List[str] = None,
                    description: str = "") -> str:
        """Create a new authentication token"""
        if permissions is None:
            permissions = ["read"]
        
        # Generate new token
        new_token = self._generate_token()
        token_hash = self._hash_token(new_token)
        
        # Load current auth data
        with open(self.config_path, 'r') as f:
            auth_data = json.load(f)
        
        # Add new token
        auth_data["tokens"][name] = {
            "token_hash": token_hash,
            "permissions": permissions,
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "active": True,
            "description": description
        }
        
        # Save updated data
        with open(self.config_path, 'w') as f:
            json.dump(auth_data, f, indent=2)
        
        logger.info(f"🔑 New token created for {name}")
        return new_token
    
    def revoke_token(self, name: str) -> bool:
        """Revoke a token by name"""
        with open(self.config_path, 'r') as f:
            auth_data = json.load(f)
        
        if name in auth_data["tokens"]:
            auth_data["tokens"][name]["active"] = False
            auth_data["tokens"][name]["revoked_at"] = datetime.now().isoformat()
            
            with open(self.config_path, 'w') as f:
                json.dump(auth_data, f, indent=2)
            
            logger.info(f"🚫 Token revoked for {name}")
            return True
        
        return False
    
    def list_tokens(self) -> Dict[str, Dict]:
        """List all registered tokens (without exposing actual tokens)"""
        with open(self.config_path, 'r') as f:
            auth_data = json.load(f)
        
        # Return token info without hashes
        token_list = {}
        for name, info in auth_data["tokens"].items():
            token_list[name] = {
                "permissions": info.get("permissions", []),
                "created_at": info.get("created_at"),
                "last_used": info.get("last_used"),
                "active": info.get("active", False),
                "description": info.get("description", "")
            }
        
        return token_list
    
    def check_permission(self, token_name: str, permission: str) -> bool:
        """Check if a token has a specific permission"""
        with open(self.config_path, 'r') as f:
            auth_data = json.load(f)
        
        token_info = auth_data["tokens"].get(token_name)
        if not token_info or not token_info.get("active", False):
            return False
        
        return permission in token_info.get("permissions", [])
    
    def update_permissions(self, token_name: str, permissions: List[str]) -> bool:
        """Update permissions for a token"""
        with open(self.config_path, 'r') as f:
            auth_data = json.load(f)
        
        if token_name in auth_data["tokens"]:
            auth_data["tokens"][token_name]["permissions"] = permissions
            
            with open(self.config_path, 'w') as f:
                json.dump(auth_data, f, indent=2)
            
            logger.info(f"🔧 Updated permissions for {token_name}: {permissions}")
            return True
        
        return False
    
    def _generate_token(self) -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(32)
    
    def _hash_token(self, token: str) -> str:
        """Hash a token for secure storage"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def get_auth_stats(self) -> Dict:
        """Get authentication statistics"""
        with open(self.config_path, 'r') as f:
            auth_data = json.load(f)
        
        active_tokens = sum(1 for t in auth_data["tokens"].values() if t.get("active", False))
        total_tokens = len(auth_data["tokens"])
        
        # Find most recently used token
        most_recent = None
        most_recent_time = None
        for name, info in auth_data["tokens"].items():
            if info.get("last_used"):
                used_time = datetime.fromisoformat(info["last_used"])
                if most_recent_time is None or used_time > most_recent_time:
                    most_recent = name
                    most_recent_time = used_time
        
        return {
            "total_tokens": total_tokens,
            "active_tokens": active_tokens,
            "most_recent_access": most_recent,
            "most_recent_time": most_recent_time.isoformat() if most_recent_time else None,
            "settings": auth_data.get("settings", {})
        }
    
    def close(self):
        """Clean shutdown"""
        logger.info("🏁 Archie: Authentication manager shutting down")