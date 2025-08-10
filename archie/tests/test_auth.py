"""
Comprehensive tests for archie_core.auth module - Device authentication system
"""
import pytest
import tempfile
import jwt
import time
import base64
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from archie_core.auth import (
    DeviceAuthManager, get_device_auth_manager, require_device_auth,
    SECRET_KEY, JWT_ISS, JWT_EXP_DAYS, VALID_SCOPES
)
from archie_core.models import DeviceRegisterRequest, DeviceTokenResponse
from archie_core.db import Database


class TestDeviceAuthManager:
    """Test DeviceAuthManager class"""
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test database"""
        with tempfile.TemporaryDirectory(prefix="archie_auth_test_") as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def auth_manager(self, temp_db_dir):
        """Create test auth manager with isolated database"""
        with patch('archie_core.auth.Database') as mock_db_class:
            db = Database(temp_db_dir)
            db.initialize()
            mock_db_class.return_value = db
            
            manager = DeviceAuthManager()
            yield manager
    
    @pytest.fixture
    def test_keypair(self):
        """Generate RSA key pair for testing"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        public_key_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        
        return {
            'private_key': private_key,
            'public_key_pem': public_key_pem
        }
    
    def test_verify_public_key_valid(self, auth_manager, test_keypair):
        """Test public key verification with valid key"""
        result = auth_manager.verify_public_key(test_keypair['public_key_pem'])
        assert result is True
    
    def test_verify_public_key_invalid(self, auth_manager):
        """Test public key verification with invalid key"""
        # Test completely invalid key
        result = auth_manager.verify_public_key("invalid key data")
        assert result is False
        
        # Test valid format but too small key size (1024 bits)
        small_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=1024,  # Too small
            backend=default_backend()
        )
        
        small_key_pem = small_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        
        result = auth_manager.verify_public_key(small_key_pem)
        assert result is False
    
    def test_verify_public_key_non_rsa(self, auth_manager):
        """Test public key verification with non-RSA key"""
        from cryptography.hazmat.primitives.asymmetric import ed25519
        
        # Generate Ed25519 key (not RSA)
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        
        result = auth_manager.verify_public_key(public_key_pem)
        assert result is False
    
    def test_register_device_valid(self, auth_manager, test_keypair):
        """Test device registration with valid data"""
        request = DeviceRegisterRequest(
            device_name="percy_device",
            public_key=test_keypair['public_key_pem'],
            scopes=["memory.read", "memory.write", "council.deliberate"],
            device_type="laptop",
            os_version="macOS 14.0",
            app_version="1.0.0"
        )
        
        result = auth_manager.register_device(request)
        
        assert 'device_id' in result
        assert 'token' in result
        assert 'scopes' in result
        assert 'expires_at' in result
        assert result['scopes'] == request.scopes  # Auto-approved for percy
        assert isinstance(result['expires_at'], datetime)
    
    def test_register_device_auto_approve(self, auth_manager, test_keypair):
        """Test auto-approval for known devices"""
        for device_name in ["percy", "archie", "admin_device"]:
            request = DeviceRegisterRequest(
                device_name=device_name,
                public_key=test_keypair['public_key_pem'],
                scopes=["admin.system", "admin.devices"]
            )
            
            result = auth_manager.register_device(request)
            assert result['scopes'] == request.scopes
    
    def test_register_device_manual_approval(self, auth_manager, test_keypair):
        """Test manual approval for unknown devices"""
        request = DeviceRegisterRequest(
            device_name="unknown_device",
            public_key=test_keypair['public_key_pem'],
            scopes=["admin.system", "admin.devices"]
        )
        
        result = auth_manager.register_device(request)
        
        # Should get limited scopes pending approval
        assert result['scopes'] == ["memory.read", "files.read"]
        assert set(result['scopes']) != set(request.scopes)
    
    def test_register_device_invalid_public_key(self, auth_manager):
        """Test device registration with invalid public key"""
        request = DeviceRegisterRequest(
            device_name="test_device",
            public_key="invalid public key",
            scopes=["memory.read"]
        )
        
        with pytest.raises(HTTPException) as exc_info:
            auth_manager.register_device(request)
        
        assert exc_info.value.status_code == 400
        assert "Invalid public key" in exc_info.value.detail
    
    def test_register_device_invalid_scopes(self, auth_manager, test_keypair):
        """Test device registration with invalid scopes"""
        request = DeviceRegisterRequest(
            device_name="test_device",
            public_key=test_keypair['public_key_pem'],
            scopes=["invalid.scope", "another.invalid"]
        )
        
        with pytest.raises(HTTPException) as exc_info:
            auth_manager.register_device(request)
        
        assert exc_info.value.status_code == 400
        assert "Invalid scopes" in exc_info.value.detail
    
    def test_generate_device_token(self, auth_manager):
        """Test JWT token generation"""
        device_id = "test_device_123"
        scopes = ["memory.read", "memory.write"]
        
        token = auth_manager.generate_device_token(device_id, scopes)
        
        # Decode token to verify contents
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"], issuer=JWT_ISS)
        
        assert payload['sub'] == device_id
        assert payload['scopes'] == scopes
        assert payload['iss'] == JWT_ISS
        assert 'exp' in payload
        assert 'iat' in payload
        assert 'jti' in payload  # Token ID
    
    def test_verify_device_token_valid(self, auth_manager, test_keypair):
        """Test token verification with valid token"""
        # First register a device
        request = DeviceRegisterRequest(
            device_name="percy",
            public_key=test_keypair['public_key_pem'],
            scopes=["memory.read", "council.deliberate"]
        )
        
        registration = auth_manager.register_device(request)
        token = registration['token']
        
        # Verify the token
        device_info = auth_manager.verify_device_token(token)
        
        assert device_info is not None
        assert device_info['device_id'] == registration['device_id']
        assert device_info['device_name'] == "percy"
        assert device_info['scopes'] == request.scopes
        assert device_info['council_member'] == "percy"
    
    def test_verify_device_token_with_scope_check(self, auth_manager, test_keypair):
        """Test token verification with required scope"""
        # Register device with limited scopes
        request = DeviceRegisterRequest(
            device_name="percy",
            public_key=test_keypair['public_key_pem'],
            scopes=["memory.read"]
        )
        
        registration = auth_manager.register_device(request)
        token = registration['token']
        
        # Should succeed with required scope device has
        device_info = auth_manager.verify_device_token(token, "memory.read")
        assert device_info is not None
        
        # Should fail with scope device doesn't have
        device_info = auth_manager.verify_device_token(token, "admin.system")
        assert device_info is None
    
    def test_verify_device_token_expired(self, auth_manager):
        """Test token verification with expired token"""
        device_id = "test_device"
        scopes = ["memory.read"]
        
        # Create expired token (exp in the past)
        past_exp = int(time.time()) - 3600  # 1 hour ago
        payload = {
            'sub': device_id,
            'scopes': scopes,
            'iss': JWT_ISS,
            'exp': past_exp,
            'iat': int(time.time()) - 7200,  # 2 hours ago
            'jti': "test_token_id"
        }
        
        expired_token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        
        # Should return None for expired token
        device_info = auth_manager.verify_device_token(expired_token)
        assert device_info is None
    
    def test_verify_device_token_invalid_signature(self, auth_manager):
        """Test token verification with invalid signature"""
        # Create token with wrong secret
        device_id = "test_device"
        scopes = ["memory.read"]
        
        payload = {
            'sub': device_id,
            'scopes': scopes,
            'iss': JWT_ISS,
            'exp': int(time.time()) + 3600,
            'iat': int(time.time()),
            'jti': "test_token_id"
        }
        
        bad_token = jwt.encode(payload, "wrong_secret", algorithm="HS256")
        
        # Should return None for invalid signature
        device_info = auth_manager.verify_device_token(bad_token)
        assert device_info is None
    
    def test_verify_device_token_device_not_found(self, auth_manager):
        """Test token verification when device not found in database"""
        # Create valid token for non-existent device
        device_id = "nonexistent_device"
        scopes = ["memory.read"]
        
        payload = {
            'sub': device_id,
            'scopes': scopes,
            'iss': JWT_ISS,
            'exp': int(time.time()) + 3600,
            'iat': int(time.time()),
            'jti': "test_token_id"
        }
        
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        
        # Should return None when device doesn't exist
        device_info = auth_manager.verify_device_token(token)
        assert device_info is None
    
    def test_renew_device_token(self, auth_manager, test_keypair):
        """Test token renewal"""
        # Register device first
        request = DeviceRegisterRequest(
            device_name="archie",
            public_key=test_keypair['public_key_pem'],
            scopes=["memory.read", "memory.write"]
        )
        
        registration = auth_manager.register_device(request)
        device_id = registration['device_id']
        
        # Renew token
        new_token = auth_manager.renew_device_token(device_id)
        
        assert new_token is not None
        assert new_token != registration['token']  # Should be different
        
        # Verify new token works
        device_info = auth_manager.verify_device_token(new_token)
        assert device_info is not None
        assert device_info['device_id'] == device_id
    
    def test_renew_device_token_not_found(self, auth_manager):
        """Test token renewal for non-existent device"""
        new_token = auth_manager.renew_device_token("nonexistent_device")
        assert new_token is None
    
    def test_update_device_capabilities(self, auth_manager, test_keypair):
        """Test updating device capabilities"""
        # Register device first
        request = DeviceRegisterRequest(
            device_name="percy",
            public_key=test_keypair['public_key_pem'],
            scopes=["memory.read"]
        )
        
        registration = auth_manager.register_device(request)
        device_id = registration['device_id']
        
        # Update capabilities
        new_capabilities = ["memory.read", "memory.write", "admin.system"]
        result = auth_manager.update_device_capabilities(device_id, new_capabilities)
        
        assert result is True
        
        # Verify capabilities were updated
        device = auth_manager.db.get_device(device_id)
        assert set(device['capabilities']) == set(new_capabilities)
    
    def test_update_device_capabilities_invalid_scopes(self, auth_manager, test_keypair):
        """Test updating device capabilities with invalid scopes"""
        # Register device first
        request = DeviceRegisterRequest(
            device_name="percy",
            public_key=test_keypair['public_key_pem'],
            scopes=["memory.read"]
        )
        
        registration = auth_manager.register_device(request)
        device_id = registration['device_id']
        
        # Try to update with invalid capabilities
        invalid_capabilities = ["memory.read", "invalid.scope"]
        
        with pytest.raises(ValueError) as exc_info:
            auth_manager.update_device_capabilities(device_id, invalid_capabilities)
        
        assert "Invalid scopes" in str(exc_info.value)
    
    def test_update_device_capabilities_not_found(self, auth_manager):
        """Test updating capabilities for non-existent device"""
        result = auth_manager.update_device_capabilities("nonexistent", ["memory.read"])
        assert result is False
    
    def test_list_devices(self, auth_manager, test_keypair):
        """Test listing registered devices"""
        # Register multiple devices
        devices_to_register = [
            ("percy_laptop", "percy"),
            ("archie_server", "archie"),
            ("user_phone", "unknown")
        ]
        
        for device_name, expected_council in devices_to_register:
            request = DeviceRegisterRequest(
                device_name=device_name,
                public_key=test_keypair['public_key_pem'],
                scopes=["memory.read"],
                device_type="test_device"
            )
            auth_manager.register_device(request)
        
        # List devices
        devices = auth_manager.list_devices()
        
        assert len(devices) == 3
        
        # Check device properties
        for device in devices:
            assert 'id' in device
            assert 'name' in device
            assert 'capabilities' in device
            assert 'last_seen' in device
            assert 'status' in device
            
            # Status should be 'active' for recently created devices
            assert device['status'] == 'active'
    
    def test_identify_council_member(self, auth_manager):
        """Test council member identification from device name"""
        test_cases = [
            ("percy_device", "percy"),
            ("Percy-Laptop", "percy"),
            ("PERCY", "percy"),
            ("archie_server", "archie"),
            ("Archie-PI", "archie"),
            ("admin_console", "admin"),
            ("unknown_device", None),
            ("user_phone", None)
        ]
        
        for device_name, expected in test_cases:
            result = auth_manager._identify_council_member(device_name)
            assert result == expected
    
    def test_verify_message_signature_valid(self, auth_manager, test_keypair):
        """Test message signature verification with valid signature"""
        # Register device first
        request = DeviceRegisterRequest(
            device_name="percy",
            public_key=test_keypair['public_key_pem'],
            scopes=["memory.read"]
        )
        
        registration = auth_manager.register_device(request)
        device_id = registration['device_id']
        
        # Create message and signature
        message = b"test message for signature verification"
        signature = test_keypair['private_key'].sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Verify signature
        result = auth_manager.verify_message_signature(device_id, message, signature)
        assert result is True
    
    def test_verify_message_signature_invalid(self, auth_manager, test_keypair):
        """Test message signature verification with invalid signature"""
        # Register device first
        request = DeviceRegisterRequest(
            device_name="percy",
            public_key=test_keypair['public_key_pem'],
            scopes=["memory.read"]
        )
        
        registration = auth_manager.register_device(request)
        device_id = registration['device_id']
        
        # Create message and wrong signature
        message = b"test message"
        wrong_message = b"different message"
        
        # Sign different message
        signature = test_keypair['private_key'].sign(
            wrong_message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Should fail verification
        result = auth_manager.verify_message_signature(device_id, message, signature)
        assert result is False
    
    def test_verify_message_signature_device_not_found(self, auth_manager):
        """Test message signature verification for non-existent device"""
        message = b"test message"
        signature = b"fake signature"
        
        result = auth_manager.verify_message_signature("nonexistent", message, signature)
        assert result is False


class TestGlobalFunctions:
    """Test module-level functions"""
    
    def test_get_device_auth_manager_singleton(self):
        """Test that get_device_auth_manager returns singleton"""
        manager1 = get_device_auth_manager()
        manager2 = get_device_auth_manager()
        
        assert manager1 is manager2  # Same instance
    
    @patch('archie_core.auth._device_auth_manager', None)
    def test_get_device_auth_manager_creates_new(self):
        """Test that get_device_auth_manager creates new instance when needed"""
        with patch('archie_core.auth.DeviceAuthManager') as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            
            manager = get_device_auth_manager()
            
            assert manager is mock_instance
            mock_class.assert_called_once()


class TestAuthDependencies:
    """Test FastAPI authentication dependencies"""
    
    @pytest.fixture
    def mock_request(self):
        """Create mock FastAPI request"""
        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.100"
        return request
    
    @pytest.fixture
    def valid_token(self):
        """Create valid JWT token for testing"""
        device_id = "test_device"
        scopes = ["memory.read", "memory.write"]
        
        payload = {
            'sub': device_id,
            'scopes': scopes,
            'iss': JWT_ISS,
            'exp': int(time.time()) + 3600,
            'iat': int(time.time()),
            'jti': "test_token_id"
        }
        
        return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    
    def test_require_device_auth_valid_token(self, mock_request, valid_token):
        """Test auth dependency with valid token"""
        mock_request.headers.get.return_value = f"Bearer {valid_token}"
        
        with patch('archie_core.auth.get_device_auth_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.verify_device_token.return_value = {
                'device_id': 'test_device',
                'device_name': 'test_device',
                'scopes': ['memory.read', 'memory.write'],
                'council_member': None
            }
            mock_get_manager.return_value = mock_manager
            
            auth_dep = require_device_auth()
            result = auth_dep(mock_request)
            
            assert result is not None
            assert result['device_id'] == 'test_device'
            mock_manager.verify_device_token.assert_called_once()
    
    def test_require_device_auth_no_header(self, mock_request):
        """Test auth dependency with missing authorization header"""
        mock_request.headers.get.return_value = None
        
        auth_dep = require_device_auth()
        
        with pytest.raises(HTTPException) as exc_info:
            auth_dep(mock_request)
        
        assert exc_info.value.status_code == 401
        assert "Missing authorization header" in exc_info.value.detail
    
    def test_require_device_auth_invalid_header_format(self, mock_request):
        """Test auth dependency with invalid header format"""
        mock_request.headers.get.return_value = "Invalid header format"
        
        auth_dep = require_device_auth()
        
        with pytest.raises(HTTPException) as exc_info:
            auth_dep(mock_request)
        
        assert exc_info.value.status_code == 401
        assert "Missing authorization header" in exc_info.value.detail
    
    def test_require_device_auth_invalid_token(self, mock_request, valid_token):
        """Test auth dependency with invalid token"""
        mock_request.headers.get.return_value = f"Bearer {valid_token}"
        
        with patch('archie_core.auth.get_device_auth_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.verify_device_token.return_value = None  # Invalid token
            mock_get_manager.return_value = mock_manager
            
            auth_dep = require_device_auth()
            
            with pytest.raises(HTTPException) as exc_info:
                auth_dep(mock_request)
            
            assert exc_info.value.status_code == 401
            assert "Invalid or expired token" in exc_info.value.detail
    
    def test_require_device_auth_with_required_scope(self, mock_request, valid_token):
        """Test auth dependency with required scope check"""
        mock_request.headers.get.return_value = f"Bearer {valid_token}"
        
        with patch('archie_core.auth.get_device_auth_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.verify_device_token.return_value = {
                'device_id': 'test_device',
                'device_name': 'test_device',
                'scopes': ['memory.read', 'memory.write'],
                'council_member': None
            }
            mock_get_manager.return_value = mock_manager
            
            auth_dep = require_device_auth("memory.read")
            result = auth_dep(mock_request)
            
            assert result is not None
            # Should call verify_device_token with required scope
            mock_manager.verify_device_token.assert_called_with(valid_token, "memory.read")
    
    def test_require_device_auth_updates_device_seen(self, mock_request, valid_token):
        """Test that auth dependency updates device last seen timestamp"""
        mock_request.headers.get.return_value = f"Bearer {valid_token}"
        
        with patch('archie_core.auth.get_device_auth_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.verify_device_token.return_value = {
                'device_id': 'test_device',
                'device_name': 'test_device',
                'scopes': ['memory.read'],
                'council_member': None
            }
            mock_get_manager.return_value = mock_manager
            
            auth_dep = require_device_auth()
            auth_dep(mock_request)
            
            # Should update device seen with client IP
            mock_manager.db.update_device_seen.assert_called_with('test_device', '192.168.1.100')


class TestScopeValidation:
    """Test scope validation and management"""
    
    def test_valid_scopes_list(self):
        """Test that all expected scopes are in VALID_SCOPES"""
        expected_scopes = {
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
        }
        
        assert set(VALID_SCOPES) == expected_scopes
    
    def test_scope_hierarchy_logic(self, temp_db_dir):
        """Test scope hierarchy and permission logic"""
        # This would test that admin.system implies other admin permissions
        # Or that council.summon implies council.deliberate
        # For now, just verify the scopes exist
        
        admin_scopes = [scope for scope in VALID_SCOPES if scope.startswith("admin.")]
        council_scopes = [scope for scope in VALID_SCOPES if scope.startswith("council.")]
        
        assert len(admin_scopes) == 3  # devices, jobs, system
        assert len(council_scopes) == 2  # summon, deliberate


class TestAuthConfiguration:
    """Test authentication configuration and constants"""
    
    def test_configuration_constants(self):
        """Test that configuration constants are properly set"""
        assert SECRET_KEY is not None
        assert JWT_ISS is not None
        assert JWT_EXP_DAYS > 0
        assert isinstance(JWT_EXP_DAYS, int)
    
    @patch.dict('os.environ', {
        'ARCHIE_SECRET_KEY': 'test-secret',
        'ARCHIE_JWT_ISS': 'test.local',
        'ARCHIE_JWT_EXP_DAYS': '7'
    })
    def test_configuration_from_environment(self):
        """Test reading configuration from environment variables"""
        # Re-import to get updated values
        import importlib
        import archie_core.auth
        importlib.reload(archie_core.auth)
        
        assert archie_core.auth.SECRET_KEY == 'test-secret'
        assert archie_core.auth.JWT_ISS == 'test.local'
        assert archie_core.auth.JWT_EXP_DAYS == 7


class TestEdgeCasesAndErrors:
    """Test edge cases and error conditions"""
    
    def test_malformed_jwt_handling(self, temp_db_dir):
        """Test handling of malformed JWT tokens"""
        with patch('archie_core.auth.Database') as mock_db_class:
            db = Database(temp_db_dir)
            db.initialize()
            mock_db_class.return_value = db
            
            auth_manager = DeviceAuthManager()
            
            # Test various malformed tokens
            malformed_tokens = [
                "not.a.jwt",
                "header.payload",  # Missing signature
                "",
                "header.payload.signature.extra",
                "invalid_base64.invalid_base64.invalid_base64"
            ]
            
            for token in malformed_tokens:
                result = auth_manager.verify_device_token(token)
                assert result is None
    
    def test_concurrent_device_registration(self, temp_db_dir):
        """Test handling concurrent device registration attempts"""
        # This would test race conditions in device registration
        # For now, just verify basic thread safety assumptions
        
        with patch('archie_core.auth.Database') as mock_db_class:
            db = Database(temp_db_dir)
            db.initialize()
            mock_db_class.return_value = db
            
            auth_manager = DeviceAuthManager()
            
            # Multiple managers should work independently
            auth_manager2 = DeviceAuthManager()
            
            assert auth_manager is not auth_manager2
            assert auth_manager.db is not auth_manager2.db  # Different DB instances
    
    def test_signature_verification_edge_cases(self, temp_db_dir):
        """Test edge cases in signature verification"""
        with patch('archie_core.auth.Database') as mock_db_class:
            db = Database(temp_db_dir)
            db.initialize()
            mock_db_class.return_value = db
            
            auth_manager = DeviceAuthManager()
            
            # Test with empty/invalid signatures
            edge_cases = [
                (b"message", b""),  # Empty signature
                (b"", b"signature"),  # Empty message
                (b"message", b"invalid_signature_data"),  # Invalid signature format
            ]
            
            for message, signature in edge_cases:
                result = auth_manager.verify_message_signature(
                    "nonexistent_device", message, signature
                )
                assert result is False
    
    def test_token_replay_protection(self, temp_db_dir):
        """Test token replay attack protection"""
        # JWT tokens include 'jti' (JWT ID) which could be used for replay protection
        # This test verifies the JTI is included
        
        with patch('archie_core.auth.Database') as mock_db_class:
            db = Database(temp_db_dir)
            db.initialize()
            mock_db_class.return_value = db
            
            auth_manager = DeviceAuthManager()
            
            device_id = "test_device"
            scopes = ["memory.read"]
            
            # Generate multiple tokens
            token1 = auth_manager.generate_device_token(device_id, scopes)
            token2 = auth_manager.generate_device_token(device_id, scopes)
            
            # Decode and verify JTI is different
            payload1 = jwt.decode(token1, SECRET_KEY, algorithms=["HS256"], issuer=JWT_ISS)
            payload2 = jwt.decode(token2, SECRET_KEY, algorithms=["HS256"], issuer=JWT_ISS)
            
            assert payload1['jti'] != payload2['jti']  # Different token IDs
    
    def test_database_connection_failure(self):
        """Test behavior when database connection fails"""
        with patch('archie_core.auth.Database') as mock_db_class:
            # Make database initialization fail
            mock_db_class.return_value.initialize.side_effect = Exception("DB connection failed")
            
            with pytest.raises(Exception):
                DeviceAuthManager()
    
    def test_public_key_format_variations(self, temp_db_dir):
        """Test various valid public key formats"""
        with patch('archie_core.auth.Database') as mock_db_class:
            db = Database(temp_db_dir)
            db.initialize()
            mock_db_class.return_value = db
            
            auth_manager = DeviceAuthManager()
            
            # Generate key in different formats
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            
            # PEM format (standard)
            pem_key = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode()
            
            assert auth_manager.verify_public_key(pem_key) is True
            
            # Test with extra whitespace
            pem_with_whitespace = "\n  " + pem_key + "  \n"
            # Current implementation may not handle extra whitespace
            # This documents the expected behavior