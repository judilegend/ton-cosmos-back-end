import logging
from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter()
logger = logging.getLogger(__name__)

NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"


@router.get("/reverse-geocode")
async def reverse_geocode(lat: float, lon: float):
    """
    Proxy pour l'API Nominatim OpenStreetMap (reverse geocoding).
    
    Convertit les coordonnées (lat, lon) en adresse lisible.
    Contourne le problème CORS du navigateur en passant par le backend.
    
    Args:
        lat: Latitude (ex: 48.85338052230053)
        lon: Longitude (ex: 2.6777240360950705)
    
    Returns:
        {
            "address": "Ville, Pays",
            "lat": float,
            "lon": float,
            "display_name": "Full address"
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{NOMINATIM_BASE_URL}/reverse",
                params={
                    "format": "json",
                    "lat": lat,
                    "lon": lon,
                    "zoom": 10,
                    "addressdetails": 1
                },
                headers={
                    "User-Agent": "TonCosmos/1.0 (Astrologie API)",
                    "Accept-Language": "fr"
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Nominatim error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=503,
                    detail=f"Service de géocodage indisponible. Code: {response.status_code}"
                )
            
            data = response.json()
            
            # Extraire les informations pertinentes
            address_parts = data.get("address", {})
            city = address_parts.get("city") or address_parts.get("town") or "Ville inconnue"
            country = address_parts.get("country", "Pays inconnu")
            
            return {
                "success": True,
                "address": f"{city}, {country}",
                "city": city,
                "country": country,
                "display_name": data.get("display_name", ""),
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "raw": data  # Retourner les données brutes si besoin
            }
            
    except httpx.TimeoutException:
        logger.error("Nominatim timeout")
        raise HTTPException(
            status_code=504,
            detail="Délai d'attente dépassé pour le service de géocodage"
        )
    except httpx.RequestError as e:
        logger.error(f"Nominatim request error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Erreur de connexion au service de géocodage"
        )
    except Exception as e:
        logger.error(f"Unexpected error in reverse_geocode: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erreur interne lors du géocodage"
        )


@router.get("/geocode")
async def geocode(address: str):
    """
    Proxy pour l'API Nominatim OpenStreetMap (forward geocoding).
    
    Convertit une adresse en coordonnées (lat, lon).
    
    Args:
        address: Adresse à géocoder (ex: "Paris, France")
    
    Returns:
        {
            "lat": float,
            "lon": float,
            "address": string
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{NOMINATIM_BASE_URL}/search",
                params={
                    "q": address,
                    "format": "json",
                    "limit": 1
                },
                headers={
                    "User-Agent": "TonCosmos/1.0 (Astrologie API)"
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=503,
                    detail="Service de géocodage indisponible"
                )
            
            data = response.json()
            
            if not data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Adresse non trouvée: {address}"
                )
            
            result = data[0]
            
            return {
                "success": True,
                "lat": float(result.get("lat")),
                "lon": float(result.get("lon")),
                "address": result.get("display_name", ""),
                "raw": result
            }
            
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Délai d'attente dépassé"
        )
    except Exception as e:
        logger.error(f"Geocoding error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors du géocodage"
        )
