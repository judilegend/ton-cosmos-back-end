import pytest
import time
from app.services.storage_service import StorageService

def test_signed_urls():
    storage = StorageService()
    filename = "test-file.mp3"
    
    # Generate URL with 5 seconds expiration
    signed_url = storage.generate_signed_url(filename, expires_in=5)
    
    # Extract params
    parts = signed_url.split("?")
    assert len(parts) == 2
    params = dict(p.split("=") for p in parts[1].split("&"))
    
    expires = int(params["expires"])
    signature = params["signature"]
    
    # Verify signature should succeed immediately
    assert storage.verify_signature(filename, expires, signature) is True
    
    # Verify signature for different filename should fail
    assert storage.verify_signature("wrong-file.mp3", expires, signature) is False
    
    # Verify expired signature should fail
    expired_time = int(time.time()) - 10
    assert storage.verify_signature(filename, expired_time, signature) is False
