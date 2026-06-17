import sys
import swisseph as swe
from unittest.mock import MagicMock

mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
sys.modules['weasyprint'] = mock_weasyprint
swe.set_ephe_path('/chemin/vers/ephe/local')

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac