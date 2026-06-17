import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.services.storage_service import StorageService

router = APIRouter()
storage_service = StorageService()

@router.get("/download/{filename}")
async def download_secure_file(filename: str, expires: int, signature: str):
    if not storage_service.verify_signature(filename, expires, signature):
        raise HTTPException(status_code=403, detail="Lien invalide ou expiré.")
        
    file_path = os.path.join(storage_service.local_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
        
    media_type = "application/octet-stream"
    if filename.endswith(".mp3"):
        media_type = "audio/mpeg"
    elif filename.endswith(".pdf"):
        media_type = "application/pdf"
        
    return FileResponse(file_path, media_type=media_type, filename=filename)
