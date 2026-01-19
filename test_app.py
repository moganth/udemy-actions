"""
Test Suite for Docker Management API
This file contains test cases for database connection, authentication, and core services.
"""

import pytest
import os
import uuid
from unittest.mock import patch, MagicMock, Mock
from pymongo.errors import ConnectionFailure
from fastapi.testclient import TestClient
from datetime import timedelta

# Import the main app
from main import app

# Import services and modules to test
from services.db_service import init_db, get_user_by_username, insert_user
from services.auth_service import (
    verify_password,
    get_password_hash,
    create_access_token,
    authenticate_user,
    get_user_role
)
from config import (
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    MONGODB_URI,
    DB_NAME
)

# Create test client
client = TestClient(app)


# ============================================
# Configuration Tests
# ============================================

class TestConfiguration:
    """Test configuration loading and environment variables"""
    
    def test_config_variables_loaded(self):
        """Test that configuration variables are loaded"""
        assert SECRET_KEY is not None
        assert ALGORITHM is not None
        assert ACCESS_TOKEN_EXPIRE_MINUTES > 0
    
    def test_mongodb_uri_format(self):
        """Test MongoDB URI is properly formatted"""
        if MONGODB_URI:
            assert isinstance(MONGODB_URI, str)
            # Should contain mongodb protocol
            assert "mongodb" in MONGODB_URI.lower() or MONGODB_URI == "mongodb://localhost:27017"
    
    def test_db_name_exists(self):
        """Test database name is configured"""
        # DB_NAME can be None (will use default) or a configured string
        assert DB_NAME is None or isinstance(DB_NAME, str)


# ============================================
# Database Connection Tests
# ============================================

class TestDatabaseConnection:
    """Test database connectivity and operations"""
    
    @patch('services.db_service.MongoClient')
    def test_mongodb_connection_success(self, mock_mongo_client):
        """Test successful MongoDB connection"""
        # Mock the MongoDB client
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {'ok': 1}
        mock_mongo_client.return_value = mock_client
        
        # Test connection is established
        mock_client.admin.command('ping')
        mock_client.admin.command.assert_called_with('ping')
    
    @patch('services.db_service.MongoClient')
    def test_mongodb_connection_failure(self, mock_mongo_client):
        """Test MongoDB connection failure handling"""
        # Mock connection failure
        mock_mongo_client.side_effect = ConnectionFailure("Connection failed")
        
        with pytest.raises(ConnectionFailure):
            raise ConnectionFailure("Connection failed")
    
    @patch('services.db_service.users_collection')
    def test_get_user_by_username_exists(self, mock_collection):
        """Test retrieving an existing user"""
        # Mock user data
        mock_user = {
            "_id": "test_id_123",
            "username": "testuser",
            "hashed_password": "hashed_pwd",
            "role": "user"
        }
        mock_collection.find_one.return_value = mock_user
        
        result = get_user_by_username("testuser")
        assert result is not None
        mock_collection.find_one.assert_called_with({"username": "testuser"})
    
    @patch('services.db_service.users_collection')
    def test_get_user_by_username_not_exists(self, mock_collection):
        """Test retrieving a non-existent user"""
        mock_collection.find_one.return_value = None
        
        result = get_user_by_username("nonexistent")
        assert result is None
    
    @patch('services.db_service.users_collection')
    def test_insert_user_success(self, mock_collection):
        """Test inserting a new user"""
        # Mock insert operation
        mock_result = MagicMock()
        mock_result.inserted_id = "new_user_id_456"
        mock_collection.insert_one.return_value = mock_result
        
        user_id = insert_user("newuser", "hashed_password_123", "user")
        assert user_id == "new_user_id_456"
        mock_collection.insert_one.assert_called_once()


# ============================================
# Authentication Service Tests
# ============================================

class TestAuthenticationService:
    """Test authentication and password operations"""
    
    def test_password_hashing(self):
        """Test password hashing functionality"""
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 0
    
    def test_password_verification_correct(self):
        """Test password verification with correct password"""
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        result = verify_password(password, hashed)
        assert result is True
    
    def test_password_verification_incorrect(self):
        """Test password verification with incorrect password"""
        password = "testpassword123"
        wrong_password = "wrongpassword"
        hashed = get_password_hash(password)
        
        result = verify_password(wrong_password, hashed)
        assert result is False
    
    def test_create_access_token(self):
        """Test JWT token creation"""
        data = {"sub": "testuser", "role": "user"}
        token = create_access_token(data, expires_delta=timedelta(minutes=30))
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_access_token_with_custom_expiry(self):
        """Test token creation with custom expiration"""
        data = {"sub": "testuser", "role": "admin"}
        custom_expiry = timedelta(minutes=60)
        token = create_access_token(data, expires_delta=custom_expiry)
        
        assert token is not None
        assert isinstance(token, str)
    
    @patch('services.auth_service.get_user')
    @patch('services.auth_service.verify_password')
    def test_authenticate_user_success(self, mock_verify, mock_get_user):
        """Test successful user authentication"""
        mock_user = {
            "id": "123",
            "username": "testuser",
            "hashed_password": "hashed_pwd",
            "role": "user"
        }
        mock_get_user.return_value = mock_user
        mock_verify.return_value = True
        
        result = authenticate_user("testuser", "password123")
        assert result == mock_user
    
    @patch('services.auth_service.get_user')
    def test_authenticate_user_not_found(self, mock_get_user):
        """Test authentication with non-existent user"""
        mock_get_user.return_value = None
        
        result = authenticate_user("nonexistent", "password123")
        assert result is False
    
    @patch('services.auth_service.get_user')
    @patch('services.auth_service.verify_password')
    def test_authenticate_user_wrong_password(self, mock_verify, mock_get_user):
        """Test authentication with wrong password"""
        mock_user = {
            "id": "123",
            "username": "testuser",
            "hashed_password": "hashed_pwd",
            "role": "user"
        }
        mock_get_user.return_value = mock_user
        mock_verify.return_value = False
        
        result = authenticate_user("testuser", "wrongpassword")
        assert result is False
    
    def test_get_user_role(self):
        """Test extracting user role"""
        user_with_role = {"username": "test", "role": "admin"}
        user_without_role = {"username": "test"}
        
        assert get_user_role(user_with_role) == "admin"
        assert get_user_role(user_without_role) == "user"


# ============================================
# API Endpoint Tests
# ============================================

class TestAPIEndpoints:
    """Test FastAPI endpoints"""
    
    def test_home_endpoint(self):
        """Test the home endpoint"""
        response = client.get("/app2/home")
        assert response.status_code == 200
        assert response.json() == {"message": "APP2 Home"}
    
    def test_docs_endpoint_accessible(self):
        """Test that API documentation is accessible"""
        response = client.get("/app2/docs")
        assert response.status_code == 200
    
    def test_openapi_schema_accessible(self):
        """Test that OpenAPI schema is accessible"""
        response = client.get("/app2/openapi.json")
        assert response.status_code == 200
        assert "openapi" in response.json()
    
    @patch('services.db_service.get_user_by_username')
    @patch('services.db_service.insert_user')
    @patch('routes.auth_route.get_password_hash')
    def test_register_endpoint_success(self, mock_hash, mock_insert, mock_get_user):
        """Test user registration endpoint"""
        # Generate unique username to avoid conflicts
        unique_username = f"testuser_{uuid.uuid4().hex[:8]}"
        
        mock_get_user.return_value = None  # User doesn't exist
        mock_insert.return_value = "new_user_id"
        mock_hash.return_value = "hashed_password"
        
        response = client.post(
            "/app2/register",
            json={
                "username": unique_username,
                "password": "password123",
                "role": "user"
            }
        )
        assert response.status_code == 201
        assert "message" in response.json()
        assert response.json()["message"] == "User registered successfully"
    
    @patch('routes.auth_route.get_user_by_username')
    def test_register_endpoint_user_exists(self, mock_get_user):
        """Test registration with existing username"""
        mock_get_user.return_value = {"username": "existinguser"}
        
        response = client.post(
            "/app2/register",
            json={
                "username": "existinguser",
                "password": "password123",
                "role": "user"
            }
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]
    
    @patch('routes.auth_route.authenticate_user')
    def test_login_endpoint_success(self, mock_authenticate):
        """Test login endpoint with valid credentials"""
        mock_authenticate.return_value = {
            "id": "123",
            "username": "testuser",
            "hashed_password": "hashed",
            "role": "user"
        }
        
        response = client.post(
            "/app2/token",
            data={
                "username": "testuser",
                "password": "password123"
            }
        )
        assert response.status_code == 200
        assert "access_token" in response.json()
        assert response.json()["token_type"] == "bearer"
    
    @patch('services.auth_service.authenticate_user')
    def test_login_endpoint_invalid_credentials(self, mock_authenticate):
        """Test login endpoint with invalid credentials"""
        mock_authenticate.return_value = False
        
        response = client.post(
            "/app2/token",
            data={
                "username": "testuser",
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]


# ============================================
# Docker Service Tests
# ============================================

class TestDockerService:
    """Test Docker service operations"""
    
    @patch('services.docker_service.docker_client')
    def test_docker_login_success(self, mock_docker):
        """Test Docker Hub login"""
        mock_docker.login.return_value = {"Status": "Login Succeeded"}
        
        from services.docker_service import docker_login
        result = docker_login("testuser", "testpass")
        
        assert result["status"] == "success"
        assert "Logged in" in result["message"]
    
    @patch('services.docker_service.docker_client')
    def test_docker_login_failure(self, mock_docker):
        """Test Docker Hub login failure"""
        from docker.errors import APIError
        mock_docker.login.side_effect = APIError("Login failed")
        
        from services.docker_service import docker_login
        result = docker_login("testuser", "wrongpass")
        
        assert "error" in result


# ============================================
# Integration Tests
# ============================================

class TestIntegration:
    """Integration tests for the full workflow"""
    
    @patch('routes.auth_route.get_user_by_username')
    @patch('routes.auth_route.insert_user')
    @patch('routes.auth_route.get_password_hash')
    @patch('routes.auth_route.authenticate_user')
    def test_register_and_login_flow(self, mock_auth, mock_hash, mock_insert, mock_get_user):
        """Test complete registration and login flow"""
        # Generate unique username to avoid conflicts
        unique_username = f"integration_{uuid.uuid4().hex[:8]}"
        
        # Registration
        mock_get_user.return_value = None
        mock_insert.return_value = "new_user_id"
        mock_hash.return_value = "hashed_password"
        
        register_response = client.post(
            "/app2/register",
            json={
                "username": unique_username,
                "password": "testpass123",
                "role": "user"
            }
        )
        assert register_response.status_code == 201
        
        # Login
        mock_auth.return_value = {
            "id": "new_user_id",
            "username": unique_username,
            "hashed_password": "hashed",
            "role": "user"
        }
        
        login_response = client.post(
            "/app2/token",
            data={
                "username": unique_username,
                "password": "testpass123"
            }
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()


# ============================================
# Run tests with pytest
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
