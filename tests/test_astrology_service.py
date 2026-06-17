import pytest
from datetime import date, time
from app.services.astrology_service import AstrologyService

@pytest.fixture
def astro_service():
    return AstrologyService()

@pytest.mark.asyncio
async def test_get_full_chart_structure(astro_service):
    b_date = date(2026, 1, 1)
    b_time = time(12, 0)
    tz_name = "Europe/Paris"
    lat, lon = 48.8566, 2.3522
    
    result = await astro_service.get_full_chart(
        b_date=b_date,
        b_time=b_time,
        tz_name=tz_name,
        lat=lat,
        lon=lon
    )
    
    assert "birth_chart" in result
    assert "forecast" in result
    
    birth_chart = result["birth_chart"]
    assert "planets" in birth_chart
    assert "ascendant" in birth_chart
    assert "houses" in birth_chart
    assert "aspects" in birth_chart
    
    assert birth_chart["planets"]["Soleil"]["sign"] == "Capricorne"
    assert isinstance(birth_chart["aspects"], list)
    assert len(result["forecast"]) == 12
    
    found_feb = any("Février 2026" in item["period"] or "February 2026" in item["period"] for item in result["forecast"])
    
    periods = [item["period"] for item in result["forecast"]]
    assert found_feb, f"Le mois de février est absent des périodes générées : {periods}"