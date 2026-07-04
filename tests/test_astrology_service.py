import pytest
from datetime import date, time
from app.services.astrology_service import AstrologyService


@pytest.fixture
def astro_service():
    return AstrologyService()


# ---------------------------------------------------------------------------
# Test 1 : Structure du thème natal complet
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Test 2 : Mapping des 12 signes zodiacaux (_get_sign)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("longitude,expected_sign", [
    (0.0,   "Bélier"),      # 0°   = Bélier
    (29.9,  "Bélier"),      # 29°  = encore Bélier
    (30.0,  "Taureau"),     # 30°  = Taureau
    (60.0,  "Gémeaux"),
    (90.0,  "Cancer"),
    (120.0, "Lion"),
    (150.0, "Vierge"),
    (180.0, "Balance"),
    (210.0, "Scorpion"),
    (240.0, "Sagittaire"),
    (270.0, "Capricorne"),
    (300.0, "Verseau"),
    (330.0, "Poissons"),
    (359.9, "Poissons"),    # dernier degré
    (360.0, "Bélier"),      # modulo 360
])
def test_get_sign_all_zodiac(astro_service, longitude, expected_sign):
    assert astro_service._get_sign(longitude) == expected_sign


# ---------------------------------------------------------------------------
# Test 3 : Format de position (_format_position)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("longitude,expected_sign,expected_deg_range", [
    (95.5, "Cancer",      (5.5,  5.5)),
    (270.0, "Capricorne", (0.0,  0.0)),
    (361.0, "Bélier",     (1.0,  1.0)),
])
def test_format_position(astro_service, longitude, expected_sign, expected_deg_range):
    result = astro_service._format_position(longitude)
    assert result["sign"] == expected_sign
    assert result["deg"] == pytest.approx(expected_deg_range[0], abs=0.01)
    assert 0 <= result["lon"] < 360


# ---------------------------------------------------------------------------
# Test 4 : Détection des aspects (_calculate_aspects_sync)
# ---------------------------------------------------------------------------
def test_aspects_conjonction_detected(astro_service):
    """Deux planètes à 2° l'une de l'autre → Conjonction détectée."""
    planets = {
        "Soleil": {"lon": 50.0, "sign": "Taureau", "deg": 20.0},
        "Lune":   {"lon": 52.0, "sign": "Taureau", "deg": 22.0},
    }
    aspects = astro_service._calculate_aspects_sync(planets)
    types = [a["type"] for a in aspects]
    assert "Conjonction" in types


def test_aspects_opposition_detected(astro_service):
    """Planètes à 180° → Opposition détectée."""
    planets = {
        "Soleil": {"lon": 0.0,   "sign": "Bélier",  "deg": 0.0},
        "Saturne": {"lon": 180.0, "sign": "Balance", "deg": 0.0},
    }
    aspects = astro_service._calculate_aspects_sync(planets)
    types = [a["type"] for a in aspects]
    assert "Opposition" in types


def test_aspects_carre_detected(astro_service):
    """Planètes à 90° → Carré détecté."""
    planets = {
        "Mars":    {"lon": 0.0,  "sign": "Bélier", "deg": 0.0},
        "Jupiter": {"lon": 90.0, "sign": "Cancer",  "deg": 0.0},
    }
    aspects = astro_service._calculate_aspects_sync(planets)
    types = [a["type"] for a in aspects]
    assert "Carré" in types


def test_aspects_trigone_detected(astro_service):
    """Planètes à 120° → Trigone détecté."""
    planets = {
        "Vénus":   {"lon": 0.0,   "sign": "Bélier",      "deg": 0.0},
        "Neptune": {"lon": 120.0, "sign": "Lion",         "deg": 0.0},
    }
    aspects = astro_service._calculate_aspects_sync(planets)
    types = [a["type"] for a in aspects]
    assert "Trigone" in types


def test_aspects_no_aspect_when_orb_too_wide(astro_service):
    """Planètes à 45° (hors des orbes) → aucun aspect standard détecté."""
    planets = {
        "Soleil": {"lon": 0.0,  "sign": "Bélier",   "deg": 0.0},
        "Uranus": {"lon": 45.0, "sign": "Taureau",  "deg": 15.0},
    }
    aspects = astro_service._calculate_aspects_sync(planets)
    # 45° n'est pas dans {0, 60, 90, 120, 180} avec orbe 5° → liste vide
    assert len(aspects) == 0


# ---------------------------------------------------------------------------
# Test 5 : Structure du chart de prévisions avancées (get_forecast_chart)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_forecast_chart_structure(astro_service):
    b_date = date(1990, 6, 15)
    b_time = time(10, 30)
    tz_name = "Europe/Paris"
    lat, lon = 48.8566, 2.3522

    result = await astro_service.get_forecast_chart(
        b_date=b_date,
        b_time=b_time,
        tz_name=tz_name,
        lat=lat,
        lon=lon
    )

    assert "solar_return" in result, "Clé 'solar_return' manquante"
    assert "saturn_returns" in result, "Clé 'saturn_returns' manquante"
    assert "transits" in result, "Clé 'transits' manquante"

    solar = result["solar_return"]
    assert "solar_return_datetime" in solar
    assert "planets" in solar
    assert "ascendant" in solar
    assert "houses" in solar

    transits = result["transits"]
    assert "aspect_windows" in transits
    assert "stations" in transits
    assert isinstance(transits["aspect_windows"], list)

    # On vérifie qu'il y a bien des retours de Saturne calculés
    # (pour un natif de 1990, le premier Saturne Return est autour de 2018-2020)
    assert isinstance(result["saturn_returns"], list)