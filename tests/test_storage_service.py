from app.services import storage_service


def test_generate_signed_url_uses_public_base_url(monkeypatch):
    monkeypatch.setattr(storage_service.settings, "PUBLIC_BASE_URL", "https://api.ton-cosmos.com")
    monkeypatch.setattr(storage_service.settings, "BACKEND_URL", "http://localhost:8000")

    url = storage_service.StorageService().generate_signed_url("audio-50.mp3")

    assert url.startswith("https://api.ton-cosmos.com/api/v1/storage/download/audio-50.mp3?")
    assert "localhost" not in url
