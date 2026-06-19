import os
import httpx
import logging
from app.core.config import settings
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        self.api_key = getattr(settings, "ELEVENLABS_API_KEY", None)
        # Standard ElevenLabs voice ID (e.g., Rachel) or fallback
        self.voice_id = getattr(settings, "ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        self.storage_service = StorageService()

    async def generate_speech(self, text: str, output_filename: str) -> str:
        """Converts text to speech using ElevenLabs and saves it. Returns the signed download URL."""
        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY not configured. Generating a mock audio file.")
            # Create a mock 1-second silence MP3 file or simple placeholder
            # A valid tiny MP3 file structure in bytes:
            mock_mp3_bytes = (
                b'\xff\xfb\x90\x44\x00\x00\x00\x03\x48\x00\x00\x00\x00\x4c\x41\x4d'
                b'\x45\x33\x2e\x39\x39\x72\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            )
            local_path = self.storage_service.save_content(mock_mp3_bytes, output_filename)
            logger.info(f"Mock audio file saved to {local_path}")
            return self.storage_service.generate_signed_url(output_filename)

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.75,
                "similarity_boost": 0.85
            }
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(url, json=data, headers=headers)
                if response.status_code != 200:
                    logger.error(f"ElevenLabs API error: {response.status_code} - {response.text}")
                    raise Exception(f"TTS generation failed: {response.text}")
                
                # Save audio to secure storage
                local_path = self.storage_service.save_content(response.content, output_filename)
                logger.info(f"TTS audio file generated and saved to {local_path}")
                
                return self.storage_service.generate_signed_url(output_filename)
            except Exception as e:
                logger.error(f"Error calling ElevenLabs API: {e}")
                # Fallback to mock file on failure
                logger.warning("Falling back to generating a mock audio file.")
                mock_mp3_bytes = b'\xff\xfb\x90\x00' * 50
                self.storage_service.save_content(mock_mp3_bytes, output_filename)
                return self.storage_service.generate_signed_url(output_filename)
