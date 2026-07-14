import pytest
from datetime import date, time
from app.services.astrology_service import AstrologyService

@pytest.fixture
def astro_service():
    return AstrologyService()

@pytest.mark.asyncio
async def test_get_forecast_chart_structure(astro_service):
    b_date = date(1995, 6, 15)
    b_time = time(8, 30)
    tz_name = "Europe/Paris"
    lat, lon = 48.8566, 2.3522
    
    result = await astro_service.get_forecast_chart(
        b_date=b_date,
        b_time=b_time,
        tz_name=tz_name,
        lat=lat,
        lon=lon
    )
    
    assert "solar_return" in result
    assert "saturn_returns" in result
    assert "transits" in result
    assert "natal_sun_longitude" in result
    assert "natal_saturn_longitude" in result
    
    # Check solar return
    sr = result["solar_return"]
    assert "solar_return_jd" in sr
    assert "solar_return_datetime" in sr
    assert "planets" in sr
    assert "ascendant" in sr
    assert "houses" in sr
    assert "Chiron" in sr["planets"]
    
    # Check Saturn Returns
    saturn_ret = result["saturn_returns"]
    assert isinstance(saturn_ret, list)
    for sr_item in saturn_ret:
        assert "return_number" in sr_item
        assert "approximate_age_range" in sr_item
        assert "exact_dates" in sr_item
        assert isinstance(sr_item["exact_dates"], list)
        
    # Check Transits
    transits = result["transits"]
    assert "aspect_windows" in transits
    assert "stations" in transits
    assert isinstance(transits["aspect_windows"], list)
    assert isinstance(transits["stations"], list)
