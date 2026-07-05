import os
import httpx
import logging
from app.core.config import settings
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

# ElevenLabs character limit per request
ELEVENLABS_CHAR_LIMIT = 4900


class TTSService:
    def __init__(self):
        self.api_key = getattr(settings, "ELEVENLABS_API_KEY", None)
        self.voice_id = getattr(settings, "ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        self.storage_service = StorageService()

    async def generate_speech(self, text: str, output_filename: str) -> str:
        """Converts text to speech using ElevenLabs and saves it. Returns the signed download URL."""
        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY not configured. Skipping TTS generation.")
            raise ValueError("ELEVENLABS_API_KEY is not set.")

        # Truncate safely to avoid exceeding API limits
        text = text.strip()
        if len(text) > ELEVENLABS_CHAR_LIMIT:
            text = text[:ELEVENLABS_CHAR_LIMIT]
            logger.warning(f"TTS text truncated to {ELEVENLABS_CHAR_LIMIT} chars.")

        if not text:
            raise ValueError("TTS text is empty — cannot generate audio.")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.75,
                "similarity_boost": 0.85,
            },
        }

        logger.info(f"Calling ElevenLabs TTS API (voice={self.voice_id}, chars={len(text)})")

        # Stream the response to handle large audio files without memory issues
        audio_chunks: list[bytes] = []
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    # Read the error body for diagnosis
                    error_body = await response.aread()
                    logger.error(
                        f"ElevenLabs API error: HTTP {response.status_code} — {error_body.decode(errors='replace')}"
                    )
                    raise Exception(
                        f"ElevenLabs TTS failed with status {response.status_code}: {error_body.decode(errors='replace')}"
                    )

                content_type = response.headers.get("content-type", "")
                if "audio" not in content_type:
                    error_body = await response.aread()
                    logger.error(
                        f"ElevenLabs returned non-audio content-type '{content_type}': {error_body.decode(errors='replace')}"
                    )
                    raise Exception(
                        f"ElevenLabs returned unexpected content-type '{content_type}'. Response: {error_body.decode(errors='replace')}"
                    )

                async for chunk in response.aiter_bytes(chunk_size=4096):
                    audio_chunks.append(chunk)

        audio_bytes = b"".join(audio_chunks)
        if len(audio_bytes) < 1024:
            # Something went wrong — likely an error response was saved as MP3
            raise Exception(
                f"ElevenLabs returned suspiciously small audio ({len(audio_bytes)} bytes). "
                "Check API key, voice ID, and account quota."
            )

        local_path = self.storage_service.save_content(audio_bytes, output_filename)
        logger.info(f"TTS audio saved to {local_path} ({len(audio_bytes)} bytes)")

        return self.storage_service.generate_signed_url(output_filename)
