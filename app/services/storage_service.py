import os
import hmac
import hashlib
import time
import shutil
from typing import Optional
from app.core.config import settings

class StorageService:
    def __init__(self):
        # Local secure storage path inside the container
        self.local_dir = "/app/static/storage"
        os.makedirs(self.local_dir, exist_ok=True)
        
    def save_file(self, source_path: str, filename: str) -> str:
        """Saves a local file to the secure storage and returns the destination path."""
        dest_path = os.path.join(self.local_dir, filename)
        shutil.copy(source_path, dest_path)
        return dest_path

    def save_content(self, content: bytes, filename: str) -> str:
        """Saves bytes content directly to a file in secure storage."""
        dest_path = os.path.join(self.local_dir, filename)
        with open(dest_path, "wb") as f:
            f.write(content)
        return dest_path
        
    def generate_signed_url(self, filename: str, expires_in: int = 604800) -> str:
        """Generates a secure relative HMAC-signed URL that expires in expires_in seconds."""
        expiration = int(time.time()) + expires_in
        message = f"{filename}:{expiration}"
        
        sig = hmac.new(
            settings.SESSION_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"/api/v1/storage/download/{filename}?expires={expiration}&signature={sig}"

    def verify_signature(self, filename: str, expires: int, signature: str) -> bool:
        """Verifies if the signature is valid and the URL has not expired."""
        if time.time() > expires:
            return False
            
        message = f"{filename}:{expires}"
        expected_sig = hmac.new(
            settings.SESSION_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_sig)
